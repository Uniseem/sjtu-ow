"""The homepage's open tournaments, the team page's record, and what refreshes them.

Until round 056 the homepage context set ``open_tournaments = None`` with a
comment saying M4 would fill it in, and the team page's record said "coming in
a later milestone". Design 13.13.4's table of regeneration events was also
only half done: approving a registration refreshed nothing at all.
"""

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


def _tournament(title, *, opens, closes, status=TournamentStatus.PUBLISHED):
    now = timezone.now()
    return Tournament.objects.create(
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
    # Round 082 (design 5.2 v3.0): 近期安排 is only what is open now, and the
    # homepage no longer has an arena block for what opens soon.
    start = html.index('aria-labelledby="agenda-title"')
    next_up = html[start : html.index("</aside>", start)]

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


@pytest.mark.django_db
def test_the_homepage_says_so_when_nothing_is_open(client, homepage):
    html = client.get("/").content.decode("utf-8")
    assert "最近没有安排" in html


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
