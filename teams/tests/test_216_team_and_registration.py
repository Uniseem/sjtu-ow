"""Round 216: teams and registration fixes from the review (T3–T6, T8, and
removing the captain).

Each test here goes red when its fix is taken out (AGENTS rule 7).
"""

from datetime import timedelta

import pytest
from django.db import transaction
from django.urls import reverse
from django.utils import timezone

from accounts.models import ContactMethod, ContactType, GameAccount, User
from core.models import SiteSettings
from teams import services
from teams.models import ApplicationStatus, Team, TeamApplication, TeamRole
from tournaments import registration as reg
from tournaments.models import (
    IndividualSignup,
    Registration,
    Tournament,
    TournamentStatus,
)

PICK_AGAIN = "游戏 ID 选择有误"
TWENTY_DIGITS = "9" * 20


def _player(email, nickname):
    now = timezone.now()
    user = User.objects.create_user(
        email=email,
        password="Correct-Horse-Battery-1",
        nickname=nickname,
        is_sjtu=True,
        agreed_terms_at=now,
        agreed_cross_border_at=now,
    )
    GameAccount.objects.create(
        user=user, battletag=f"{nickname}#2160", rank_tank=30, rank_damage=20
    )
    ContactMethod.objects.create(user=user, type=ContactType.QQ, value="123456789")
    return user


def _superuser():
    return User.objects.create_superuser(
        email="root216@example.com",
        password="Correct-Horse-Battery-1",
        nickname="站长216",
        agreed_terms_at=timezone.now(),
        agreed_cross_border_at=timezone.now(),
    )


def _tournament(**kwargs):
    now = timezone.now()
    options = {
        "title": "216 杯",
        "registration_opens_at": now - timedelta(days=1),
        "registration_closes_at": now + timedelta(days=7),
        "roster_min": 2,
        "roster_max": 3,
        "status": TournamentStatus.PUBLISHED,
        "published_at": now,
        "registration_mode": "team",
    }
    options.update(kwargs)
    return Tournament.objects.create(**options)


@pytest.fixture
def captain(db):
    return _player("cap216@example.com", "队长216")


@pytest.fixture
def mate(db):
    return _player("mate216@example.com", "队员216")


@pytest.fixture
def team(captain, mate):
    team = services.create_team(user=captain, name="二一六战队")
    application = services.apply_to_team(team=team, user=mate, roles={"tank": True})
    services.approve_application(application=application, actor=captain)
    return team


def _selections(team):
    return {
        str(membership.user.pk): membership.user.game_accounts.first().pk
        for membership in team.memberships.all()
    }


# --- T3: the game ID picked on the team registration form -----------------------


@pytest.mark.django_db
@pytest.mark.parametrize("garbage", ["abc", TWENTY_DIGITS])
def test_resolve_accounts_takes_garbage_without_crashing(team, mate, garbage):
    """216 T3: ``account-<pk>`` comes straight from the form. "abc" handed to a
    primary-key lookup was a ValueError (a 500); now it is a problem to show.
    (A 20-digit number already came back empty from the lookup on Django 6,
    so that case is a guard against a regression, not a red-without-fix.)"""
    selections = _selections(team)
    selections[str(mate.pk)] = garbage

    chosen, problems = reg._resolve_accounts(reg.team_members(team), selections)

    assert any(PICK_AGAIN in problem for problem in problems)
    assert set(chosen) == {membership.user_id for membership in team.memberships.all()}


@pytest.mark.django_db
@pytest.mark.parametrize("garbage", ["abc", TWENTY_DIGITS])
def test_submit_refuses_a_garbage_game_id(team, captain, mate, garbage):
    """216 T3: the whole submission is refused with「游戏 ID 选择有误」and
    nothing is written."""
    tournament = _tournament()
    selections = _selections(team)
    selections[str(mate.pk)] = garbage

    with pytest.raises(reg.RegistrationError) as exc:
        reg.submit(
            tournament=tournament, team=team, actor=captain, selections=selections
        )

    assert PICK_AGAIN in str(exc.value)
    assert not Registration.objects.filter(tournament=tournament).exists()


@pytest.mark.django_db
@pytest.mark.parametrize("garbage", ["abc", TWENTY_DIGITS])
def test_register_page_shows_the_problem_for_a_garbage_game_id(
    client, team, captain, mate, garbage
):
    """216 T3: through the captain's page the same POST is a 200 that says
    what is wrong, not a 500 (the test client re-raises the view's error)."""
    tournament = _tournament()
    client.force_login(captain)
    fields = {
        f"account-{user_pk}": account_pk
        for user_pk, account_pk in _selections(team).items()
    }
    fields[f"account-{mate.pk}"] = garbage

    response = client.post(
        reverse("tournament_register", args=[tournament.pk]),
        {"action": "submit", "team": team.pk, **fields},
    )

    assert response.status_code == 200
    assert any(PICK_AGAIN in problem for problem in response.context["problems"])
    assert PICK_AGAIN in response.content.decode()
    assert not Registration.objects.filter(tournament=tournament).exists()


# --- T4: assign_captain is one transaction ----------------------------------------


@pytest.mark.django_db
def test_a_refused_assign_captain_leaves_nobody_on_the_team(team, captain):
    """216 T4: assigning someone who already captains the most teams one may
    lead is refused by transfer_captain, after assign_captain had already put
    them on the team. The membership must roll back with the refusal."""
    site = SiteSettings.load()
    site.team_max_captained = 1
    site.save()
    busy = _player("busy216@example.com", "忙队长216")
    services.create_team(user=busy, name="忙队长的队")
    assert services.captained_count(busy) == services.max_captained()

    with pytest.raises(services.TeamError, match="已达上限"):
        services.assign_captain(team=team, actor=_superuser(), new_captain=busy)

    assert not team.memberships.filter(user=busy).exists()
    assert team.captain() == captain


# --- T5: applying twice, and creating under the captain cap ----------------------


@pytest.mark.django_db
def test_a_second_pending_application_is_a_team_error(team, monkeypatch):
    """216 T5: a double click sent two requests that both passed can_apply's
    「还有一条待审批的申请」; the second hit the database constraint, an
    IntegrityError (a 500). Bypass the check to stand in for the race."""
    applicant = _player("twice216@example.com", "点两下216")
    services.apply_to_team(team=team, user=applicant, roles={"tank": True})
    monkeypatch.setattr(services, "can_apply", lambda team, user: (True, ""))

    with pytest.raises(services.TeamError, match="待审批的申请"):
        services.apply_to_team(team=team, user=applicant, roles={"damage": True})

    pending = TeamApplication.objects.filter(
        team=team, applicant=applicant, status=ApplicationStatus.PENDING
    )
    assert pending.count() == 1


@pytest.mark.django_db
def test_create_team_checks_its_limits_inside_the_transaction(captain, monkeypatch):
    """216 T5: the captain cap and the name are checked inside the write
    transaction, so two creates at once cannot both pass them. The test
    itself runs in a transaction, so ``in_atomic_block`` is always true here;
    what tells is one more atomic block when the checks run."""
    connection = transaction.get_connection()
    depth_outside = len(connection.atomic_blocks)
    seen = {}
    real_blocker = services.create_blocker
    real_name_taken = services.name_taken

    def blocker(user):
        seen["blocker"] = len(connection.atomic_blocks)
        return real_blocker(user)

    def name_taken(name, exclude_pk=None):
        seen["name_taken"] = len(connection.atomic_blocks)
        return real_name_taken(name, exclude_pk)

    monkeypatch.setattr(services, "create_blocker", blocker)
    monkeypatch.setattr(services, "name_taken", name_taken)

    services.create_team(user=captain, name="事务里查的队")

    assert seen["blocker"] > depth_outside
    assert seen["name_taken"] > depth_outside


# --- T6: a form that does not validate does not use the day's quota ---------------


@pytest.mark.django_db
def test_invalid_create_forms_do_not_use_up_the_daily_limit(client, captain):
    """216 T6: three tries with a taken name used to count against the three
    teams a day (CREATE_LIMIT), so the fourth, valid, try was refused."""
    from django.core.cache import cache

    from teams.views import CREATE_LIMIT

    services.create_team(user=_player("other216@example.com", "别人216"), name="占名队")
    founder = _player("founder216@example.com", "创始人216")
    client.force_login(founder)
    cache.clear()
    for _ in range(CREATE_LIMIT):
        response = client.post(
            reverse("team_create"),
            {"name": "占名队", "description": "", "is_recruiting": "on"},
        )
        assert response.status_code == 200
        assert response.context["form"].errors["name"] == [services.NAME_TAKEN]

    response = client.post(
        reverse("team_create"),
        {"name": "新起的队", "description": "", "is_recruiting": "on"},
        follow=True,
    )

    assert "今天创建的战队太多了" not in response.content.decode()
    assert Team.objects.filter(name="新起的队").count() == 1


# --- T8: an ad-hoc roster from a pool entry whose game ID is gone -----------------


@pytest.mark.django_db
def test_forming_a_team_from_an_entry_without_a_game_id(captain):
    """216 T8: a pool entry's game ID can be deleted (SET_NULL). Writing the
    ad-hoc roster read ``account.battletag`` and crashed; now the row is
    written with an empty battletag and no ranks, as _write_roster does."""
    tournament = _tournament(registration_mode="individual")
    entries = []
    for index in range(2):
        user = _player(f"pool216-{index}@example.com", f"散人216-{index}")
        entries.append(
            reg.sign_up_individual(
                tournament=tournament,
                user=user,
                game_account_id=user.game_accounts.first().pk,
                roles=["tank"],
            )
        )
    gone = entries[0]
    IndividualSignup.objects.filter(pk=gone.pk).update(game_account=None)

    reg.form_teams(
        tournament=tournament,
        actor=_superuser(),
        layout=[
            {
                "registration_id": None,
                "name": "散人一队",
                "signup_ids": [entry.pk for entry in entries],
            }
        ],
    )

    registration = tournament.registrations.get()
    row = registration.members.get(user=gone.user)
    assert row.game_account is None
    assert row.battletag == ""
    assert (row.rank_tank, row.rank_damage, row.rank_support) == (None, None, None)
    other = registration.members.get(user=entries[1].user)
    assert other.battletag == "散人216-1#2160"


# --- removing the captain ----------------------------------------------------------


@pytest.mark.django_db
def test_a_superuser_cannot_remove_the_captain(team, captain):
    """216: a superuser passed remove_member's「只有队长」check and could
    remove the captain, leaving the team with none. The captaincy has to be
    handed over first."""
    with pytest.raises(services.TeamError, match="不能移除队长"):
        services.remove_member(team=team, actor=_superuser(), member_user=captain)

    assert team.memberships.get(user=captain).role == TeamRole.CAPTAIN
