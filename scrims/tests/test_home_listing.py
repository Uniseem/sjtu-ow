"""The homepage's "upcoming scrims" block and what refreshes it (design 5.1, 13.13.4).

Until round 056 the homepage context set ``upcoming_scrims = None`` and the
block always said the feature was coming in a later milestone.
"""

from datetime import timedelta

import pytest
from django.core.management import call_command
from django.utils import timezone

from core.models import PrerenderedPage
from scrims import services
from scrims.models import ScrimStatus
from scrims.tests.test_scrims import make_scrim


@pytest.fixture
def homepage(db):
    call_command("init_site", verbosity=0)


@pytest.fixture
def prerender_on(settings, tmp_path):
    settings.PRERENDER_ENABLED = True
    settings.PRERENDER_ROOT = tmp_path


def _in(days, **kwargs):
    return make_scrim(starts_at=timezone.now() + timedelta(days=days), **kwargs)


@pytest.mark.django_db
def test_the_homepage_lists_the_next_seven_days(client, homepage):
    _in(2, title="后天的内战")
    _in(6.9, title="快满七天的内战")
    _in(7.1, title="超过七天的内战")
    _in(-0.1, title="已经开始的内战")
    _in(2, title="草稿内战", status=ScrimStatus.DRAFT)
    _in(2, title="取消的内战", status=ScrimStatus.CANCELLED)

    html = client.get("/").content.decode("utf-8")

    assert "后天的内战" in html
    assert "快满七天的内战" in html
    for hidden in ("超过七天的内战", "已经开始的内战", "草稿内战", "取消的内战"):
        assert hidden not in html, hidden
    assert "后续里程碑" not in html


@pytest.mark.django_db
def test_upcoming_scrims_start_soonest_first(db):
    later = _in(5, title="晚")
    sooner = _in(1, title="早")
    assert services.upcoming_scrims() == [sooner, later]


@pytest.mark.django_db
def test_the_homepage_says_so_when_there_are_none(client, homepage):
    assert "未来 7 天没有内战" in client.get("/").content.decode("utf-8")


@pytest.mark.django_db
def test_publishing_a_scrim_refreshes_the_homepage(prerender_on):
    scrim = _in(3, status=ScrimStatus.DRAFT)
    services.publish(scrim=scrim)
    assert "/" in set(PrerenderedPage.objects.values_list("path", flat=True))


@pytest.mark.django_db
def test_the_homepage_is_refreshed_as_the_scrim_enters_the_window_and_starts(
    prerender_on, django_capture_on_commit_callbacks
):
    """Entering the 7-day window and starting both change the block."""
    from django_tasks_db.models import DBTaskResult

    scrim = _in(10, status=ScrimStatus.DRAFT)
    with django_capture_on_commit_callbacks(execute=True):
        services.publish(scrim=scrim)

    home_runs = {
        row.run_after
        for row in DBTaskResult.objects.filter(task_path="core.tasks.prerender_page")
        if row.args_kwargs["args"] == ["/"]
    }
    # Besides the immediate refresh that publishing itself asks for.
    assert {
        scrim.starts_at - timedelta(days=services.HOME_SCRIM_DAYS),
        scrim.starts_at,
    } <= home_runs


@pytest.mark.django_db
@pytest.mark.parametrize(
    "action, start",
    [
        (services.publish, ScrimStatus.DRAFT),
        (services.finish, ScrimStatus.PUBLISHED),
        (services.cancel_scrim, ScrimStatus.PUBLISHED),
    ],
)
def test_the_admin_buttons_refresh_the_static_pages(prerender_on, action, start):
    """Only the edit form used to refresh them; the buttons left pages stale."""
    scrim = _in(3, status=start)
    action(scrim=scrim)
    requested = set(PrerenderedPage.objects.values_list("path", flat=True))
    assert {"/scrims/", f"/scrims/{scrim.pk}/", "/"} <= requested
