"""The homepage's open tournaments, the team page's record, and what refreshes them.

Until round 056 the homepage context set ``open_tournaments = None`` with a
comment saying M4 would fill it in, and the team page's record said "coming in
a later milestone". Design 13.13.4's table of regeneration events was also
only half done: approving a registration refreshed nothing at all.
"""

import re
from datetime import timedelta

import pytest
from django.utils import timezone

from core.models import PrerenderedPage
from tournaments import registration as reg
from tournaments import services
from tournaments.models import RegistrationStatus, Tournament, TournamentStatus
from tournaments.tests.test_state_table import _force, admin_user

APPROVED = RegistrationStatus.APPROVED
PENDING = RegistrationStatus.PENDING


DAY = timedelta(days=1)


def _tournament(title, *, opens, closes, status=TournamentStatus.PUBLISHED):
    now = timezone.now()
    return Tournament.objects.create(
        registration_mode="team",
        title=title,
        registration_opens_at=now + opens,
        registration_closes_at=now + closes,
        roster_min=2,
        roster_max=3,
        status=status,
        published_at=now if status != TournamentStatus.DRAFT else None,
    )


@pytest.fixture
def prerender_on(settings, tmp_path):
    settings.PRERENDER_ENABLED = True
    settings.PRERENDER_ROOT = tmp_path


def _requested():
    return set(PrerenderedPage.objects.values_list("path", flat=True))


@pytest.fixture
def homepage(db):
    """Without init_site the test database has no HomePage at /."""
    from django.core.management import call_command

    call_command("init_site", verbosity=0)


# --- homepage ------------------------------------------------------------------


@pytest.mark.django_db
def test_the_homepage_lists_tournaments_open_for_registration(client, homepage):
    day = timedelta(days=1)
    _tournament("报名中的赛事", opens=-day, closes=day)
    _tournament("还没开始报名的赛事", opens=day, closes=2 * day)
    _tournament("已经截止的赛事", opens=-2 * day, closes=-day)
    _tournament("草稿赛事", opens=-day, closes=day, status=TournamentStatus.DRAFT)
    _tournament("取消的赛事", opens=-day, closes=day, status=TournamentStatus.CANCELLED)

    html = client.get("/").content.decode("utf-8")
    # 近期 (design 5.2): one open now wins over the rest (v6.66 shows the
    # others only when nothing is open).
    start = html.index('aria-labelledby="home-upcoming"')
    next_up = html[start : html.index("</section>", start)]

    assert "报名中的赛事" in next_up
    assert "还没开始报名的赛事" not in next_up
    for hidden in ("还没开始报名的赛事", "已经截止的赛事", "草稿赛事", "取消的赛事"):
        assert hidden not in html, hidden
    assert "后续里程碑" not in html


@pytest.mark.django_db
def test_open_tournaments_close_soonest_first():
    day = timedelta(days=1)
    later = _tournament("后截止", opens=-day, closes=3 * day)
    sooner = _tournament("先截止", opens=-day, closes=day)
    assert services.open_tournaments() == [sooner, later]


def _card(client):
    html = client.get("/").content.decode("utf-8")
    start = html.index('aria-labelledby="home-upcoming"')
    upcoming = html[start : html.index("</section>", start)]
    match = re.search(r'<article class="c-feature".*?</article>', upcoming, re.S)
    return match.group(0) if match else upcoming


@pytest.mark.django_db
def test_the_homepage_says_so_when_there_is_no_tournament(client, homepage):
    """v6.66 (round 188): an empty card in the same place, not nothing."""
    _tournament("草稿赛事", opens=-DAY, closes=DAY, status=TournamentStatus.DRAFT)
    _tournament("取消的赛事", opens=-DAY, closes=DAY, status=TournamentStatus.CANCELLED)
    card = _card(client)
    assert 'data-next-up="no-tournament"' in card and "还没有赛事" in card


@pytest.mark.django_db
def test_without_one_open_the_next_one_not_over_is_shown(client, homepage):
    """v6.66 (round 188): until then the card vanished once registration
    closed. The soonest of those still ahead, with its phase."""
    _tournament(
        "最近结束的赛事",
        opens=-9 * DAY,
        closes=-8 * DAY,
        status=TournamentStatus.FINISHED,
    )
    later = _tournament("下个月开放报名", opens=30 * DAY, closes=40 * DAY)
    later.starts_at = timezone.now() + 45 * DAY
    later.save(update_fields=["starts_at"])
    closed = _tournament("报名已截止的赛事", opens=-3 * DAY, closes=-DAY)
    closed.starts_at = timezone.now() + 2 * DAY
    closed.save(update_fields=["starts_at"])

    card = _card(client)
    assert "报名已截止的赛事" in card and 'data-phase="closed"' in card
    assert ">报名已截止</span>" in card

    closed.delete()
    card = _card(client)
    assert "下个月开放报名" in card and ">即将开始报名</span>" in card
    assert "开放报名" in card and "已通过" not in card


@pytest.mark.django_db
def test_when_all_are_over_the_last_one_is_shown(client, homepage):
    old = _tournament(
        "去年的赛事",
        opens=-400 * DAY,
        closes=-390 * DAY,
        status=TournamentStatus.FINISHED,
    )
    old.starts_at = timezone.now() - 380 * DAY
    old.save(update_fields=["starts_at"])
    last = _tournament(
        "上个月的赛事",
        opens=-40 * DAY,
        closes=-35 * DAY,
        status=TournamentStatus.FINISHED,
    )
    last.starts_at = timezone.now() - 30 * DAY
    last.save(update_fields=["starts_at"])

    card = _card(client)
    assert "上个月的赛事" in card and ">已结束</span>" in card
    assert "去年的赛事" not in card

    # The chooser itself, given both (the homepage only passes the last).
    from content.home import feature_tournament

    assert feature_tournament([old, last]).tournament == last
    assert feature_tournament([last, old]).phase == "finished"


# --- team page -----------------------------------------------------------------


@pytest.mark.django_db
def test_the_team_page_lists_approved_entries_only(client, make):
    approved, _captain, team, _ = make()
    _force(approved, APPROVED)
    pending_tournament = _tournament(
        "还在审核的赛事", opens=-timedelta(days=1), closes=timedelta(days=1)
    )
    pending = approved.__class__.objects.create(
        tournament=pending_tournament, team=team, team_name=team.name, status=PENDING
    )
    assert pending.status == PENDING

    html = client.get(team.get_absolute_url()).content.decode("utf-8")

    assert approved.tournament.title in html
    assert "还在审核的赛事" not in html
    assert "后续里程碑" not in html


@pytest.mark.django_db
def test_a_draft_tournament_stays_off_the_team_page(make):
    registration, _captain, team, _ = make()
    _force(registration, APPROVED)
    Tournament.objects.filter(pk=registration.tournament_id).update(
        status=TournamentStatus.DRAFT
    )
    assert services.team_entries(team) == []


# --- what refreshes them (design 13.13.4) ---------------------------------------


@pytest.mark.django_db
def test_a_tournament_change_refreshes_the_homepage(prerender_on):
    day = timedelta(days=1)
    tournament = _tournament("改了的赛事", opens=-day, closes=day)
    services.after_change(tournament)
    assert "/" in _requested()


@pytest.mark.django_db
def test_registration_opening_and_closing_refresh_the_homepage(prerender_on):
    from django_tasks_db.models import DBTaskResult

    day = timedelta(days=1)
    tournament = _tournament("下周开始报名", opens=day, closes=2 * day)
    services.after_change(tournament)

    home_runs = sorted(
        row.run_after
        for row in DBTaskResult.objects.filter(task_path="core.tasks.prerender_page")
        if row.args_kwargs["args"] == ["/"]
    )
    assert home_runs == [
        tournament.registration_opens_at,
        tournament.registration_closes_at,
    ]


@pytest.mark.django_db
def test_approving_refreshes_the_tournament_and_team_pages(prerender_on, make):
    registration, _captain, team, _ = make()
    PrerenderedPage.objects.all().delete()

    reg.approve(registration=registration, actor=admin_user())

    # v3.0: the homepage's 近期安排 shows the approved count too (13.13.4).
    assert {
        registration.tournament.get_absolute_url(),
        team.get_absolute_url(),
        "/",
    } <= _requested()


@pytest.mark.django_db
def test_revoking_an_approval_refreshes_them_too(prerender_on, make):
    registration, _captain, team, _ = make()
    _force(registration, APPROVED)
    PrerenderedPage.objects.all().delete()

    reg.reject(registration=registration, actor=admin_user(), note="资格有问题")

    assert team.get_absolute_url() in _requested()


@pytest.mark.django_db
def test_syncing_an_approved_roster_refreshes_the_team_page(prerender_on, make):
    """A sync sends the registration back to pending, off the team's record."""
    registration, captain, team, selections = make()
    _force(registration, APPROVED)
    PrerenderedPage.objects.all().delete()

    reg.submit(
        tournament=registration.tournament,
        team=team,
        actor=captain,
        selections=selections,
    )

    assert team.get_absolute_url() in _requested()


@pytest.mark.django_db
def test_changes_that_never_touch_approval_refresh_nothing(prerender_on, make):
    registration, _captain, team, _ = make()
    PrerenderedPage.objects.all().delete()

    reg.reject(registration=registration, actor=admin_user(), note="资料不全")

    assert team.get_absolute_url() not in _requested()
