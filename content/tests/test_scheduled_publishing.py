"""Round 158: times set under 「设置计划」 take effect (design 12.5, 16.5, v6.50)."""

from datetime import timedelta
from unittest import mock

import pytest
from django.core.cache import cache
from django.core.management import call_command
from django.utils import timezone

from content.models import ArticleCategory, ArticleIndexPage, ArticlePage
from content.services import publish_due_pages
from core import prerender, worker
from core.health import WORKER_HEARTBEAT_CACHE_KEY
from core.models import PrerenderedPage
from core.tests.test_prerender import _article, _user


@pytest.fixture
def site_tree(db):
    call_command("init_site", verbosity=0)


@pytest.fixture
def prerender_root(settings, tmp_path):
    settings.PRERENDER_ENABLED = True
    settings.PRERENDER_ROOT = tmp_path
    prerender.forget_targets()


def _at(moment):
    """Move the clock, for Wagtail as well as for us."""
    return mock.patch("django.utils.timezone.now", return_value=moment)


def _one_beat(publish):
    """Run the worker's loop once on this thread: the heartbeat asks it to
    stop, so it ends after this beat whatever ``publish`` does. It closes its
    database connection after each step, which here is the test's own."""
    real_heartbeat = worker.write_worker_heartbeat

    def heartbeat_then_stop():
        real_heartbeat()
        worker._stop.set()

    worker._stop.clear()
    with (
        mock.patch("core.worker.write_worker_heartbeat", heartbeat_then_stop),
        mock.patch("content.services.publish_due_pages", publish),
        mock.patch("core.worker.close_old_connections"),
    ):
        worker._heartbeat_loop()
    worker._stop.clear()


def _scheduled(go_live_at):
    page = ArticlePage(
        title="周五公告158",
        slug="friday-158",
        category=ArticleCategory.objects.first(),
        summary="到点上线。",
        owner=_user("scheduler158@example.com"),
        live=False,
    )
    ArticleIndexPage.objects.live().first().add_child(instance=page)
    page.go_live_at = go_live_at
    page.save_revision().publish()
    page.refresh_from_db()
    assert not page.live  # Wagtail only noted the time
    return page


@pytest.mark.django_db
def test_a_scheduled_article_goes_live_when_its_time_comes(site_tree, prerender_root):
    go_live_at = timezone.now() + timedelta(hours=2)
    page = _scheduled(go_live_at)

    with mock.patch("django.core.management.call_command") as run:
        assert publish_due_pages() is False  # not yet: nothing runs
    run.assert_not_called()

    PrerenderedPage.objects.all().delete()
    with _at(go_live_at + timedelta(seconds=30)):
        assert publish_due_pages() is True
    page.refresh_from_db()
    assert page.live
    paths = set(PrerenderedPage.objects.values_list("path", flat=True))
    assert {page.url, "/"} <= paths  # the article, and the homepage that lists it


@pytest.mark.django_db
def test_an_article_comes_down_when_it_expires(site_tree, prerender_root):
    page = _article(title="报名截止前158", slug="expiring-158")
    expire_at = timezone.now() + timedelta(days=1)
    page.expire_at = expire_at
    page.save_revision().publish()
    page.refresh_from_db()
    assert page.live
    url = page.url

    with _at(expire_at + timedelta(seconds=30)):
        with mock.patch("core.prerender.request_removal") as remove:
            assert publish_due_pages() is True
    page.refresh_from_db()
    assert not page.live and page.expired
    remove.assert_called_with(url)


@pytest.mark.django_db
def test_the_worker_does_it_on_every_beat(db):
    calls = []

    _one_beat(lambda: calls.append(1))
    assert calls == [1]


@pytest.mark.django_db
def test_a_failure_does_not_stop_the_heartbeat(db, caplog):
    def broken():
        raise RuntimeError("数据库锁住了")

    cache.delete(WORKER_HEARTBEAT_CACHE_KEY)
    _one_beat(broken)  # returns instead of raising
    assert cache.get(WORKER_HEARTBEAT_CACHE_KEY)
    assert "Failed to publish scheduled pages" in caplog.text


@pytest.mark.django_db
def test_the_admin_manual_says_where_the_schedule_is(site_tree):
    from accounts.tests.test_onboarding import _user as role_user
    from core.admin_manual import parts_for

    def text(user):
        return "".join(step.text for part in parts_for(user) for step in part.steps)

    editor = text(role_user("c158@example.com", "内容编辑", "投稿者"))
    author = text(role_user("a158@example.com", "认证作者", "投稿者"))
    for steps in (editor, author):
        # v7.0: the back office's article form has the group for it.
        assert "「网址和发布时间」" in steps and "定时上线" in steps
