"""Round 119: the small things left from the admin review
(handoff/rounds/115-admin-review/findings.md, 「其他（小）」 and #29).

The admin's own buttons in Wagtail's action log, the AI's read on a
submission's edit page, the typography preview beside its form, the roster
minimum checked before saving, lists without a query per row, and one
shared piece of markup for status buttons and page links.
"""

from datetime import timedelta
from pathlib import Path

import pytest
from allauth.account.models import EmailAddress
from django.conf import settings as django_settings
from django.contrib.auth.models import Group
from django.core.management import call_command
from django.db import connection
from django.test.utils import CaptureQueriesContext
from django.urls import reverse
from django.utils import timezone
from wagtail.log_actions import registry as log_registry
from wagtail.models import ModelLogEntry

from accounts.models import Feature, FeatureGroupRestriction, FeatureUserRule, User
from accounts.services import GROUP_SUBMITTER
from content.models import ArticleCategory, ArticleIndexPage, ArticlePage
from core.models import SiteSettings
from moderation.models import ModerationItem, Risk, TargetType
from scrims.models import Scrim, ScrimFormat, ScrimStatus
from tournaments import registration as reg
from tournaments.models import Tournament, TournamentStatus
from tournaments.tests.test_state_table import player

PASSWORD = "Correct-Horse-Battery-1"


@pytest.fixture
def site(db):
    call_command("init_site", verbosity=0)


def _staff(email, *groups, superuser=False):
    user = User.objects.create_user(
        email=email,
        password=PASSWORD,
        nickname=email.split("@")[0][:12],
        is_superuser=superuser,
        agreed_terms_at=timezone.now(),
        agreed_cross_border_at=timezone.now(),
    )
    EmailAddress.objects.create(user=user, email=email, verified=True, primary=True)
    for name in groups:
        user.groups.add(Group.objects.get(name=name))
    return user


def _logged(instance, action):
    return ModelLogEntry.objects.for_instance(instance).filter(action=action)


def _tournament(**extra):
    now = timezone.now()
    values = {
        "title": "记录杯",
        "registration_mode": "team",
        "registration_opens_at": now - timedelta(days=1),
        "registration_closes_at": now + timedelta(days=7),
        "roster_min": 2,
        "roster_max": 3,
        "status": TournamentStatus.DRAFT,
    }
    values.update(extra)
    return Tournament.objects.create(**values)


def _article(author, title="AI 看过的稿件"):
    news = ArticleIndexPage.objects.get(slug="news")
    page = ArticlePage(
        title=title,
        slug=f"ai-read-{ArticlePage.objects.count()}",
        category=ArticleCategory.objects.filter(allow_submission=True).first(),
        author=author,
        owner=author,
        summary="摘要",
        body="正文",
    )
    news.add_child(instance=page)
    page.save_revision(user=author)
    page.unpublish()
    return ArticlePage.objects.get(pk=page.pk)


# --- the action log (design 14.4) --------------------------------------


@pytest.mark.django_db
def test_tournament_buttons_are_on_record(site, client):
    manager = _staff("log-manager119@example.com", "赛事管理员")
    client.force_login(manager)
    tournament = _tournament()
    client.post(reverse("tournament_action", args=[tournament.pk, "publish"]))
    entry = _logged(tournament, "tournaments.publish").get()
    assert entry.user == manager
    client.post(
        reverse("tournament_cancel", args=[tournament.pk]), {"reason": "场地没了"}
    )
    assert _logged(tournament, "tournaments.cancel").get().data["reason"] == "场地没了"
    assert log_registry.get_action_label("tournaments.publish") == "发布赛事"
    # The back office's 「操作记录」 (docs/admin.md 4.6) names the action.
    client.force_login(_staff("log-root119@example.com", superuser=True))
    history = client.get(reverse("backoffice:log") + "?action=tournaments.publish")
    assert "发布赛事" in history.content.decode()
    assert "记录杯" in history.content.decode()


@pytest.mark.django_db
def test_scrim_buttons_and_the_split_page_are_on_record(site, client):
    scrimmer = _staff("log-scrim119@example.com", "内战管理员")
    client.force_login(scrimmer)
    scrim = Scrim.objects.create(
        title="记录内战",
        format=ScrimFormat.OPEN_5V5,
        status=ScrimStatus.DRAFT,
        starts_at=timezone.now() + timedelta(days=1),
    )
    client.post(reverse("scrim_action", args=[scrim.pk, "publish"]))
    assert _logged(scrim, "scrims.publish").exists()
    split = reverse("scrim_split", args=[scrim.pk])
    client.post(split, {"action": "select"})
    assert _logged(scrim, "scrims.select").exists()
    client.post(split, {"action": "save"})
    assert _logged(scrim, "scrims.save_teams").exists()
    client.post(reverse("scrim_cancel", args=[scrim.pk]))
    assert _logged(scrim, "scrims.cancel").get().user == scrimmer


@pytest.mark.django_db
def test_team_rescue_actions_are_on_record(site, client):
    from teams import services as team_services

    root = _staff("log-root119@example.com", superuser=True)
    client.force_login(root)
    captain = player("log-cap119@example.com", "旧队长")
    heir = player("log-heir119@example.com", "新队长")
    team = team_services.create_team(user=captain, name="记录战队")
    client.post(reverse("team_assign_captain", args=[team.pk]), {"user": heir.pk})
    assert _logged(team, "teams.assign_captain").get().data["captain"] == "新队长"
    client.post(reverse("team_admin_disband", args=[team.pk]))
    assert _logged(team, "teams.disband").get().user == root


@pytest.mark.django_db
def test_saving_the_arrangement_board_is_on_record(site, client):
    manager = _staff("log-board119@example.com", "赛事管理员")
    client.force_login(manager)
    tournament = _tournament(
        title="编排记录杯",
        registration_mode="individual",
        status=TournamentStatus.PUBLISHED,
        published_at=timezone.now(),
    )
    client.post(
        reverse("tournament_teams_board", args=[tournament.pk]), {"action": "save"}
    )
    entry = _logged(tournament, "tournaments.arrange").get()
    assert entry.data["created"] == 0


# --- the AI's read on a submission (design 5.5.1) ----------------------


@pytest.mark.django_db
def test_editors_see_the_ai_read_on_a_submission(site, client):
    author = _staff("ai-author119@example.com", GROUP_SUBMITTER)
    page = _article(author)
    ModerationItem.objects.create(
        target_type=TargetType.ARTICLE,
        target_id=page.pk,
        field="content",
        excerpt="正文",
        text_hash="ai-read-119",
        risk=Risk.MEDIUM,
        categories=["harassment"],
        reason="有一句人身攻击",
        quote="你们都是菜鸟",
        checked_at=timezone.now(),
    )
    edit = reverse("backoffice:article_edit", args=[page.pk])
    client.force_login(_staff("ai-editor119@example.com", "内容编辑"))
    html = client.get(edit).content.decode()
    assert "AI 判断：中" in html
    assert "有一句人身攻击" in html
    assert "你们都是菜鸟" in html
    client.force_login(author)
    own = client.get(edit)
    assert own.status_code == 200
    assert "AI 判断" not in own.content.decode()


@pytest.mark.django_db
def test_a_submission_still_under_review_says_so(site, client):
    author = _staff("ai-wait-author119@example.com", GROUP_SUBMITTER)
    page = _article(author, title="AI 还没看完")
    edit = reverse("backoffice:article_edit", args=[page.pk])
    client.force_login(_staff("ai-wait-editor119@example.com", "内容编辑"))
    assert "data-ai-verdict" not in client.get(edit).content.decode()
    ModerationItem.objects.create(
        target_type=TargetType.ARTICLE,
        target_id=page.pk,
        field="content",
        excerpt="正文",
        text_hash="ai-wait-119",
    )
    assert "AI 还没巡查到这篇" in client.get(edit).content.decode()


# --- the typography preview (design 13.12) -----------------------------


@pytest.mark.django_db
def test_the_typography_preview_sits_beside_the_form(site, client):
    client.force_login(_staff("type-root119@example.com", superuser=True))
    html = client.get(reverse("core_typography")).content.decode()
    layout = html[html.index('class="typography-layout"') :]
    assert layout.index('id="typography-form"') < layout.index(
        'class="typography-aside"'
    )
    assert layout.index('class="typography-aside"') < layout.index(
        'id="typography-preview"'
    )
    css = Path(django_settings.BASE_DIR, "assets/css/input.css").read_text(
        encoding="utf-8"
    )
    start = css.index("  @media (min-width: 1200px) {\n    .typography-layout {")
    wide = css[start : css.index("\n  }\n", start)]
    assert "grid-template-columns" in wide
    assert "position: sticky" in wide


# --- the roster minimum, before saving ---------------------------------


def _tournament_form(user, **data):
    from backoffice.forms import TournamentForm

    now = timezone.now()
    values = {
        "title": "下限杯",
        "summary": "摘要",
        "registration_opens_at": (now - timedelta(days=1)).strftime("%Y-%m-%d %H:%M"),
        "registration_closes_at": (now + timedelta(days=7)).strftime("%Y-%m-%d %H:%M"),
        "registration_mode": "team",
        "roster_min": "5",
        "roster_max": "6",
    }
    values.update(data)
    form = TournamentForm(data=values, instance=Tournament(), user=user)
    form.is_valid()
    return form


@pytest.mark.django_db
def test_a_team_minimum_above_the_site_cap_is_refused_before_saving(site):
    settings = SiteSettings.load()
    settings.team_max_members = 8
    settings.save()
    manager = _staff("cap-manager119@example.com", "赛事管理员")
    refused = _tournament_form(manager, roster_min="9", roster_max="10")
    assert "没有战队能满足" in " ".join(refused.errors.get("roster_min", []))
    assert "现在是 8 人" in str(refused.fields["roster_min"].help_text)
    fine = _tournament_form(manager, roster_min="8", roster_max="10")
    assert "roster_min" not in fine.errors
    individual = _tournament_form(
        manager, roster_min="9", roster_max="10", registration_mode="individual"
    )
    assert "roster_min" not in individual.errors


# --- lists without a query per row -------------------------------------


def _queries(client, url):
    with CaptureQueriesContext(connection) as context:
        assert client.get(url).status_code == 200
    return len(context.captured_queries)


@pytest.mark.django_db
def test_feature_rule_lists_do_not_query_per_row(site, client):
    root = _staff("rows-root119@example.com", superuser=True)
    client.force_login(root)

    def add_rules(count, start):
        for index in range(start, start + count):
            user = player(f"rows{index}-119@example.com", f"规则{index}")
            FeatureUserRule.objects.create(
                user=user, feature=Feature.TEAM_CREATE, updated_by=root
            )
            group = Group.objects.create(name=f"规则组{index}")
            FeatureGroupRestriction.objects.create(
                group=group, feature=Feature.TEAM_CREATE, updated_by=root
            )

    add_rules(2, 0)
    users_few = _queries(client, reverse("backoffice:users"))
    groups_few = _queries(client, reverse("backoffice:roles"))
    add_rules(8, 2)
    assert _queries(client, reverse("backoffice:users")) == users_few
    assert _queries(client, reverse("backoffice:roles")) == groups_few


@pytest.mark.django_db
def test_the_arrangement_board_does_not_query_per_person(site, client):
    client.force_login(_staff("rows-board119@example.com", "赛事管理员"))
    tournament = _tournament(
        title="散人很多杯",
        registration_mode="individual",
        status=TournamentStatus.PUBLISHED,
        published_at=timezone.now(),
    )

    def sign_up(count, start):
        for index in range(start, start + count):
            user = player(f"pool{index}-119@example.com", f"散人{index}")
            reg.sign_up_individual(
                tournament=tournament,
                user=user,
                game_account_id=user.game_accounts.first().pk,
                roles=["tank"],
            )

    url = reverse("tournament_teams_board", args=[tournament.pk])
    sign_up(2, 0)
    few = _queries(client, url)
    sign_up(8, 2)
    assert _queries(client, url) == few


@pytest.mark.django_db
def test_my_submissions_do_not_query_per_article(site, client):
    author = _staff("rows-author119@example.com", GROUP_SUBMITTER)
    client.force_login(author)
    _article(author, title="第一篇")
    few = _queries(client, "/admin/")
    for index in range(5):
        _article(author, title=f"又一篇{index}")
    assert _queries(client, "/admin/") == few


# --- one piece of markup for status buttons and page links (#29) -------


@pytest.mark.django_db
def test_page_links_keep_the_filters(site, client):
    for index in range(30):
        ModerationItem.objects.create(
            target_type=TargetType.NICKNAME,
            target_id=index + 1,
            field="nickname",
            excerpt=f"昵称{index}",
            text_hash=f"pager-{index}",
            risk=Risk.HIGH,
            checked_at=timezone.now(),
        )
    client.force_login(_staff("pager119@example.com", "内容编辑"))
    html = client.get(
        reverse("moderation_index") + "?risk=high&since=7"
    ).content.decode()
    nav = html[html.index('aria-label="翻页"') :]
    link = nav[nav.index("href=") : nav.index(">下一页")]
    for part in ("risk=high", "since=7", "page=2"):
        assert part in link


def test_custom_admin_lists_share_the_tabs_and_the_pager():
    root = Path(django_settings.BASE_DIR)
    pager_users = [
        "moderation/templates/moderation/index.html",
        "moderation/templates/moderation/avatars.html",
        "core/templates/core/prerender/index.html",
        "tournaments/templates/tournaments/admin/review_index.html",
    ]
    tab_users = [
        "moderation/templates/moderation/avatars.html",
        "core/templates/core/prerender/index.html",
        "scrims/templates/scrims/admin/split.html",
    ]
    for name in pager_users:
        text = (root / name).read_text(encoding="utf-8")
        assert 'include "core/admin/_pager.html"' in text, name
        assert "上一页" not in text, name
    for name in tab_users:
        text = (root / name).read_text(encoding="utf-8")
        assert 'include "core/admin/_tabs.html"' in text, name
