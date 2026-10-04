"""Round 093: a tournament takes individuals (the default) or teams, never both.

Design 8.1, 8.2, 8.3, 8.4 (v5.3). The user, 2026-10-03: every tournament signs
people up one by one unless the admin says teams when publishing; then the
captain enters the whole team and nobody has to confirm.
"""

from datetime import timedelta

import pytest
from django.core import mail
from django.urls import reverse
from django.utils import timezone

from teams import services as team_services
from tournaments import registration as reg
from tournaments.models import RegistrationMode, Tournament, TournamentStatus
from tournaments.tests.test_adhoc_teams import _admin
from tournaments.tests.test_state_table import _force, player

TITLE = "报名方式赛"


def _tournament(**kwargs):
    now = timezone.now()
    options = {
        "title": TITLE,
        "registration_opens_at": now - timedelta(days=1),
        "registration_closes_at": now + timedelta(days=7),
        "roster_min": 1,
        "roster_max": 4,
        "status": TournamentStatus.PUBLISHED,
        "published_at": now,
    }
    options.update(kwargs)
    return Tournament.objects.create(**options)


def _team(prefix, size=2):
    captain = player(f"{prefix}-cap@example.com", f"{prefix}队长")
    team = team_services.create_team(user=captain, name=f"{prefix}战队")
    mates = []
    for index in range(1, size):
        mate = player(f"{prefix}-{index}@example.com", f"{prefix}队员{index}")
        application = team_services.apply_to_team(
            team=team, user=mate, roles={"tank": True}
        )
        team_services.approve_application(application=application, actor=captain)
        mates.append(mate)
    return team, captain, mates


def _selections(team):
    return {
        str(m.user.pk): m.user.game_accounts.first().pk for m in team.memberships.all()
    }


def _enter(tournament, team, captain):
    return reg.submit(
        tournament=tournament, team=team, actor=captain, selections=_selections(team)
    )


def _slot(client, tournament):
    url = reverse("state_fragment") + f"?slots=tournament-actions:{tournament.pk}"
    return client.get(url).content.decode()


def _admin_data(tournament, **changes):
    data = {
        "title": tournament.title,
        "summary": "",
        "starts_at": "",
        "registration_opens_at": tournament.registration_opens_at.strftime(
            "%Y-%m-%d %H:%M"
        ),
        "registration_closes_at": tournament.registration_closes_at.strftime(
            "%Y-%m-%d %H:%M"
        ),
        "registration_mode": tournament.registration_mode,
        "roster_min": tournament.roster_min,
        "roster_max": tournament.roster_max,
        "sjtu_only": False,
        "auto_approve": False,
    }
    data.update(changes)
    return data


def _admin_form(tournament, **changes):
    from backoffice.forms import TournamentForm

    return TournamentForm(
        _admin_data(tournament, **changes), instance=tournament, user=_admin()
    )


# --- the field ---------------------------------------------------------------------


@pytest.mark.django_db
def test_a_new_tournament_takes_individuals():
    tournament = _tournament()

    assert tournament.registration_mode == RegistrationMode.INDIVIDUAL
    assert tournament.takes_individuals and not tournament.takes_teams


@pytest.mark.django_db(transaction=True)
def test_the_old_switch_becomes_the_mode():
    """Migration 0008: tournaments that took individuals keep doing so; the
    rest took only teams and stay that way."""
    from django.db import connection
    from django.db.migrations.executor import MigrationExecutor

    before = [("tournaments", "0007_adhoc_teams")]
    after = [("tournaments", "0008_registration_mode")]
    executor = MigrationExecutor(connection)
    executor.migrate(before)
    old = executor.loader.project_state(before).apps.get_model(
        "tournaments", "Tournament"
    )
    now = timezone.now()
    window = {
        "registration_opens_at": now,
        "registration_closes_at": now + timedelta(days=1),
    }
    people = old.objects.create(
        title="开过个人报名", allow_individual_signup=True, **window
    )
    teams = old.objects.create(
        title="只收战队", allow_individual_signup=False, **window
    )

    try:
        executor = MigrationExecutor(connection)
        executor.migrate(after)
        new = executor.loader.project_state(after).apps.get_model(
            "tournaments", "Tournament"
        )

        assert new.objects.get(pk=people.pk).registration_mode == "individual"
        assert new.objects.get(pk=teams.pk).registration_mode == "team"
    finally:
        # Later tests in this process need today's tables (round 129 added a
        # column after 0008).
        executor = MigrationExecutor(connection)
        executor.migrate(executor.loader.graph.leaf_nodes())


# --- one way in ----------------------------------------------------------------------


@pytest.mark.django_db
def test_an_individual_tournament_refuses_a_team_entry():
    tournament = _tournament()
    team, captain, _mates = _team("个人赛")

    with pytest.raises(reg.RegistrationError, match="不接受战队报名"):
        _enter(tournament, team, captain)
    assert not tournament.registrations.exists()


@pytest.mark.django_db
def test_the_mode_locks_once_anyone_has_signed_up():
    """Design 8.1: a team entry or a pool entry, either one locks it."""
    open_one = _tournament(title="还没人报")
    form = _admin_form(open_one, registration_mode="team")
    assert form.is_valid(), form.errors

    alone = _tournament(title="有人个人报名")
    solo = player("lock-solo@example.com", "散人")
    reg.sign_up_individual(
        tournament=alone,
        user=solo,
        game_account_id=solo.game_accounts.first().pk,
        roles=["tank"],
    )
    form = _admin_form(alone, registration_mode="team")
    assert not form.is_valid()
    assert "不能再改「报名方式」" in form.errors["registration_mode"][0]

    teams = _tournament(title="有战队报名", registration_mode="team")
    team, captain, _mates = _team("锁定")
    _enter(teams, team, captain)
    form = _admin_form(teams, registration_mode="individual")
    assert not form.is_valid()
    assert "不能再改「报名方式」" in form.errors["registration_mode"][0]


# --- the page ------------------------------------------------------------------------


@pytest.mark.django_db
def test_the_page_says_how_people_sign_up(client):
    alone = _tournament(title="个人报名的赛")
    html = client.get(alone.get_absolute_url()).content.decode()
    assert '<span class="c-tag" data-mode-tag>个人报名</span>' in html
    assert "每人报名，管理员编队" in html
    assert "已编成的队伍" in html and "还没有编队。" in html
    assert 'id="t-pool"' in html

    teams = _tournament(title="整队报名的赛", registration_mode="team")
    html = client.get(teams.get_absolute_url()).content.decode()
    assert '<span class="c-tag" data-mode-tag>整队报名</span>' in html
    assert "队长为全队报名" in html
    assert "已通过的战队" in html
    assert 'id="t-pool"' not in html


@pytest.mark.django_db
def test_the_cards_lead_with_the_mode(client):
    alone = _tournament(title="个人卡")
    teams = _tournament(title="整队卡", registration_mode="team")
    team, captain, _mates = _team("卡片")
    reg.approve(registration=_enter(teams, team, captain), actor=_admin())
    solo = player("card-solo@example.com", "卡片散人")
    reg.sign_up_individual(
        tournament=alone,
        user=solo,
        game_account_id=solo.game_accounts.first().pk,
        roles=["tank"],
    )
    reg.form_teams(
        tournament=alone,
        actor=_admin(),
        layout=[
            {
                "registration_id": None,
                "name": "一队",
                "signup_ids": list(
                    alone.individual_signups.values_list("pk", flat=True)
                ),
            }
        ],
    )

    html = client.get("/tournaments/").content.decode()

    assert "个人报名 · 1–4 人一队 · 已编成 1 队" in html
    assert "整队报名 · 1–4 人一队 · 已通过 1 队" in html


@pytest.mark.django_db
def test_a_member_entered_by_the_captain_sees_the_team(client):
    """Nobody confirms a team entry, so the page is where a member finds it."""
    tournament = _tournament(registration_mode="team")
    team, captain, (mate,) = _team("名单")
    registration = _enter(tournament, team, captain)
    client.force_login(mate)

    fragment = _slot(client, tournament)

    assert f"你在「{team.name}」的名单里" in fragment
    assert registration.get_absolute_url() in fragment
    assert "需要由队长为战队报名" not in fragment

    _force(registration, "withdrawn")
    fragment = _slot(client, tournament)
    assert "的名单里" not in fragment
    assert "需要由队长为战队报名" in fragment


@pytest.mark.django_db
def test_the_entry_form_says_nobody_confirms(client):
    tournament = _tournament(registration_mode="team")
    team, captain, _mates = _team("说明", size=3)
    client.force_login(captain)

    html = client.get(reverse("tournament_register", args=[tournament.pk])).content
    html = html.decode()

    assert "提交后全队 3 人直接进入名单" in html
    assert "不需要队员确认" in html


# --- the members' mail ---------------------------------------------------------------


def _entered_mail():
    return {
        m.recipients()[0]: m.body
        for m in mail.outbox
        if m.subject == f"你已被报名参加：{TITLE}"
    }


@pytest.mark.django_db
def test_members_hear_when_entered_and_a_sync_tells_only_the_new(
    django_capture_on_commit_callbacks,
):
    tournament = _tournament(registration_mode="team")
    team, captain, (mate,) = _team("通知")
    mail.outbox.clear()

    with django_capture_on_commit_callbacks(execute=True):
        registration = _enter(tournament, team, captain)

    sent = _entered_mail()
    assert list(sent) == [mate.email]  # not the captain, who did it
    body = sent[mate.email]
    assert (
        f"队长 {captain.nickname} 为战队「{team.name}」报名了「{tournament.title}」"
        in body
    )
    assert f"你的游戏 ID：{mate.game_accounts.first().battletag}" in body
    assert "当前状态：待审核" in body
    assert "不需要你确认" in body

    late = player("通知-late@example.com", "后来的人")
    application = team_services.apply_to_team(
        team=team, user=late, roles={"support": True}
    )
    team_services.approve_application(application=application, actor=captain)
    mail.outbox.clear()
    with django_capture_on_commit_callbacks(execute=True):
        _enter(tournament, team, captain)  # a sync
    assert list(_entered_mail()) == [late.email]

    # A withdrawn roster holds no place: resubmitting tells everyone again.
    with django_capture_on_commit_callbacks(execute=True):
        reg.withdraw(registration=registration, actor=captain)
    mail.outbox.clear()
    with django_capture_on_commit_callbacks(execute=True):
        _enter(tournament, team, captain)
    assert sorted(_entered_mail()) == sorted([mate.email, late.email])


# --- admin and scrims -------------------------------------------------------------


@pytest.mark.django_db
def test_the_team_board_is_offered_only_where_people_sign_up_alone():
    from backoffice.views.events import tournament_items

    alone = _tournament(title="编队")
    teams = _tournament(title="不编队", registration_mode="team")

    def labels(tournament):
        return [item.label for item in tournament_items(tournament)]

    assert "队伍编排" in labels(alone)
    assert "队伍编排" not in labels(teams)


@pytest.mark.django_db
def test_a_scrim_banner_is_its_placeholder_picture(client):
    """Design 13.2.6 (v5.3): a scrim has nowhere to upload a cover, so its
    banner is its own placeholder scene instead of a plain strip."""
    from core import placeholders
    from scrims.tests.test_scrims import make_scrim

    scrim = make_scrim()

    html = client.get(reverse("scrim_detail", args=[scrim.pk])).content.decode()
    start = html.index('<header class="c-stage')
    banner = html[start : html.index("</header>", start)]

    assert "c-stage--plain" not in banner
    assert 'class="c-stage__img"' in banner
    assert placeholders.filename(placeholders.pick(scrim)) in banner
