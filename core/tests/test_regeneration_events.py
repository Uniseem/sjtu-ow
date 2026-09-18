"""The rows of design 13.13.4's regeneration table that round 057 filled in.

Round 056 walked the table and found 8 of its 14 rows incomplete; it fixed the
ones about the homepage and the team record. These are the rest: signups,
nickname changes, articles linked to a tournament, and game modes.
"""

from datetime import timedelta

import pytest
from django.core.management import call_command
from django.utils import timezone

from content.models import ArticleCategory, ArticleIndexPage, ArticlePage
from core.models import GameMode, PrerenderedPage, SiteSettings
from scrims import services as scrim_services
from scrims.tests.test_scrims import make_scrim, make_user
from teams import services as team_services
from tournaments.models import Tournament, TournamentStatus


@pytest.fixture
def prerender_on(settings, tmp_path):
    settings.PRERENDER_ENABLED = True
    settings.PRERENDER_ROOT = tmp_path


def _requested():
    return set(PrerenderedPage.objects.values_list("path", flat=True))


def _forget_requests():
    PrerenderedPage.objects.all().delete()


# --- 内战报名、修改报名、取消报名 → 活动详情 ---


@pytest.mark.django_db
def test_signing_up_and_cancelling_refresh_the_scrim_page(prerender_on):
    scrim = make_scrim()
    player = make_user("signup@example.com", "报名的人")
    account = player.game_accounts.first()

    _forget_requests()
    scrim_services.sign_up(
        scrim=scrim, user=player, game_account_id=account.pk, roles=["damage"]
    )
    assert f"/scrims/{scrim.pk}/" in _requested()

    _forget_requests()
    scrim_services.cancel(scrim=scrim, user=player)
    assert f"/scrims/{scrim.pk}/" in _requested()


# --- 用户修改昵称 → 战队主页、报名的内战、署名的文章 ---


@pytest.fixture
def famous(db):
    """A user whose nickname is printed on a team page, a scrim and an article."""
    call_command("init_site", verbosity=0)
    user = make_user("famous@example.com", "旧昵称")
    team = team_services.create_team(user=user, name="有名战队")
    scrim = make_scrim()
    scrim_services.sign_up(
        scrim=scrim,
        user=user,
        game_account_id=user.game_accounts.first().pk,
        roles=["damage"],
    )
    news = ArticleIndexPage.objects.get(slug="news")
    article = ArticlePage(
        title="署名文章",
        slug="byline",
        category=ArticleCategory.objects.get(slug="guide"),
        author=user,
        owner=user,
        summary="摘要",
        body=[("paragraph", "<p>正文</p>")],
    )
    news.add_child(instance=article)
    article.save_revision().publish()
    return user, team, scrim, ArticlePage.objects.get(pk=article.pk)


@pytest.mark.django_db
def test_a_new_nickname_refreshes_every_page_that_prints_it(prerender_on, famous):
    user, team, scrim, article = famous
    _forget_requests()

    user.nickname = "新昵称"
    user.save()

    assert {team.get_absolute_url(), f"/scrims/{scrim.pk}/", article.get_url()} <= (
        _requested()
    )


@pytest.mark.django_db
def test_logging_in_does_not_refresh_anything(prerender_on, famous):
    """A login saves the user with update_fields=["last_login"]."""
    user, team, *_ = famous
    _forget_requests()

    user.last_login = timezone.now()
    user.save(update_fields=["last_login"])
    user.save()  # a full save with the same nickname

    assert team.get_absolute_url() not in _requested()


# --- 文章变化 → 关联赛事的详情页 -----------------------------------------------------


@pytest.mark.django_db
def test_an_article_refreshes_the_tournament_it_is_linked_to(prerender_on, famous):
    user, *_ = famous
    now = timezone.now()
    tournament = Tournament.objects.create(
        title="关联赛事",
        registration_opens_at=now - timedelta(days=1),
        registration_closes_at=now + timedelta(days=1),
        roster_min=2,
        roster_max=3,
        status=TournamentStatus.PUBLISHED,
        published_at=now,
    )
    news = ArticleIndexPage.objects.get(slug="news")
    article = ArticlePage(
        title="赛事战报",
        slug="report",
        category=ArticleCategory.objects.get(slug="guide"),
        author=user,
        owner=user,
        summary="摘要",
        body=[("paragraph", "<p>正文</p>")],
        tournament=tournament,
    )
    news.add_child(instance=article)
    _forget_requests()

    article.save_revision().publish()
    assert tournament.get_absolute_url() in _requested()

    _forget_requests()
    ArticlePage.objects.get(pk=article.pk).unpublish()
    assert tournament.get_absolute_url() in _requested()


# --- 游戏模式修改 → 组队大厅外壳 ----------------------------------------------------


@pytest.mark.django_db
def test_changing_a_game_mode_refreshes_the_lfg_shell(prerender_on):
    _forget_requests()
    mode = GameMode.objects.create(name="新模式")
    assert "/lfg/" in _requested()

    _forget_requests()
    mode.delete()
    assert "/lfg/" in _requested()


# --- 后台设置的说明文字 ----------------------------------------------------------


def test_no_setting_is_still_labelled_for_a_later_milestone():
    """Round 057: nine settings in use since M3 still said 「后续里程碑使用」."""
    labels = [
        str(field.help_text)
        for field in SiteSettings._meta.get_fields()
        if getattr(field, "help_text", "")
    ]
    headings = [str(getattr(panel, "heading", "")) for panel in SiteSettings.panels]
    assert not [text for text in labels + headings if "后续里程碑" in text]
