"""Round 216, T7 (design 8.5, v7.20): no reviewing or team forming on a
tournament that was cancelled or has finished.

Before, passing a registration after the tournament was cancelled still
wrote 「报名已通过」 letters and a new line on the team's page; forming or
dissolving ad-hoc teams changed rosters of an event that was over.
"""

from datetime import timedelta

import pytest
from django.contrib.auth.models import Group
from django.core.management import call_command
from django.urls import reverse
from django.utils import timezone

from tournaments import registration as reg
from tournaments.models import (
    Registration,
    RegistrationStatus,
    Tournament,
    TournamentStatus,
)
from tournaments.tests.test_state_table import admin_user, player

PENDING = RegistrationStatus.PENDING
APPROVED = RegistrationStatus.APPROVED

CLOSED = [
    pytest.param(
        TournamentStatus.CANCELLED, "赛事已取消，不能再审核或编队。", id="cancelled"
    ),
    pytest.param(
        TournamentStatus.FINISHED, "赛事已结束，不能再审核或编队。", id="finished"
    ),
]


def _close(tournament, status):
    Tournament.objects.filter(pk=tournament.pk).update(status=status)


def _fresh(registration):
    """Reloaded, so ``registration.tournament`` is read again too."""
    return Registration.objects.select_related("tournament").get(pk=registration.pk)


def _individual_tournament():
    now = timezone.now()
    return Tournament.objects.create(
        title="散人杯216",
        registration_opens_at=now - timedelta(days=1),
        registration_closes_at=now + timedelta(days=7),
        roster_min=2,
        roster_max=3,
        status=TournamentStatus.PUBLISHED,
        published_at=now,
        registration_mode="individual",
    )


def _pool(tournament, count=2):
    entries = []
    for index in range(count):
        user = player(f"pool216-{index}@example.com", f"散人216-{index}")
        entries.append(
            reg.sign_up_individual(
                tournament=tournament,
                user=user,
                game_account_id=user.game_accounts.first().pk,
                roles=["tank"],
            )
        )
    return entries


def _new_team(name, entries):
    return [
        {
            "registration_id": None,
            "name": name,
            "signup_ids": [entry.pk for entry in entries],
        }
    ]


# --- approve / reject ----------------------------------------------------------


@pytest.mark.django_db
@pytest.mark.parametrize("status,message", CLOSED)
def test_216_t7_approving_on_a_closed_tournament_is_refused(make, status, message):
    """216, T7: 通过 on a cancelled or finished tournament."""
    registration, *_ = make(PENDING)
    _close(registration.tournament, status)
    registration = _fresh(registration)
    with pytest.raises(reg.RegistrationError) as caught:
        reg.approve(registration=registration, actor=admin_user())
    assert str(caught.value) == message
    assert _fresh(registration).status == PENDING
    assert not registration.logs.filter(action="approve").exists()


@pytest.mark.django_db
@pytest.mark.parametrize("status,message", CLOSED)
def test_216_t7_rejecting_on_a_closed_tournament_is_refused(make, status, message):
    """216, T7: 驳回 (and 撤销 of a passed one) on a closed tournament."""
    pending, *_ = make(PENDING)
    approved, *_ = make(APPROVED)
    for registration in (pending, approved):
        _close(registration.tournament, status)
        registration = _fresh(registration)
        before = registration.status
        with pytest.raises(reg.RegistrationError) as caught:
            reg.reject(registration=registration, actor=admin_user(), note="不符合")
        assert str(caught.value) == message
        assert _fresh(registration).status == before


@pytest.mark.django_db
def test_216_t7_a_published_tournament_still_reviews(make):
    """216, T7 sanity: the guard leaves an open tournament alone."""
    registration, *_ = make(PENDING)
    reg.approve(registration=_fresh(registration), actor=admin_user())
    assert _fresh(registration).status == APPROVED


# --- form_teams / dissolve -----------------------------------------------------


@pytest.mark.django_db
@pytest.mark.parametrize("status,message", CLOSED)
def test_216_t7_forming_teams_on_a_closed_tournament_is_refused(status, message):
    """216, T7: 队伍编排 saves nothing on a closed tournament."""
    tournament = _individual_tournament()
    entries = _pool(tournament)
    _close(tournament, status)
    tournament.refresh_from_db()
    with pytest.raises(reg.RegistrationError) as caught:
        reg.form_teams(
            tournament=tournament,
            actor=admin_user(),
            layout=_new_team("一队216", entries),
        )
    assert str(caught.value) == message
    assert not tournament.registrations.exists()


@pytest.mark.django_db
@pytest.mark.parametrize("status,message", CLOSED)
def test_216_t7_dissolving_on_a_closed_tournament_is_refused(status, message):
    """216, T7: 解散 a formed team after the tournament closed."""
    tournament = _individual_tournament()
    admin = admin_user()
    reg.form_teams(
        tournament=tournament,
        actor=admin,
        layout=_new_team("一队216", _pool(tournament)),
    )
    registration = tournament.registrations.get()
    assert registration.status == APPROVED
    _close(tournament, status)
    registration = _fresh(registration)
    with pytest.raises(reg.RegistrationError) as caught:
        reg.dissolve(registration=registration, actor=admin)
    assert str(caught.value) == message
    assert _fresh(registration).status == APPROVED
    assert registration.members.filter(is_active=True).count() == 2


@pytest.mark.django_db
def test_216_t7_a_published_tournament_still_forms_and_dissolves():
    """216, T7 sanity: forming and dissolving work while it is on."""
    tournament = _individual_tournament()
    admin = admin_user()
    reg.form_teams(
        tournament=tournament,
        actor=admin,
        layout=_new_team("一队216", _pool(tournament)),
    )
    registration = tournament.registrations.get()
    reg.dissolve(registration=_fresh(registration), actor=admin)
    assert _fresh(registration).status == RegistrationStatus.WITHDRAWN


# --- through the review page ---------------------------------------------------


@pytest.mark.django_db
@pytest.mark.parametrize("status,message", CLOSED)
def test_216_t7_the_review_page_says_why_and_changes_nothing(
    make, client, status, message
):
    """216, T7: 通过 pressed on the review page of a closed tournament shows
    the reason and leaves the registration pending. The reviewer is a
    赛事管理员, not a superuser."""
    call_command("init_site", verbosity=0)
    registration, *_ = make(PENDING)
    manager = player("review-manager216@example.com", "审核管理员216")
    manager.is_staff = True
    manager.save(update_fields=["is_staff"])
    manager.groups.add(Group.objects.get(name="赛事管理员"))
    assert not manager.is_superuser
    _close(registration.tournament, status)
    client.force_login(manager)
    response = client.post(
        reverse("registration_review_action", args=[registration.pk]),
        {"action": "approve"},
        follow=True,
    )
    assert response.status_code == 200
    assert message in response.content.decode()
    assert _fresh(registration).status == PENDING
