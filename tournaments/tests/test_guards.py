"""Refusals in registration and tournaments that had no test (round 059)."""

import pytest
from django.urls import reverse

from accounts.models import User
from tournaments import registration as reg
from tournaments import services
from tournaments.models import RegistrationStatus, ReviewMode, TournamentStatus
from tournaments.tests.test_state_table import admin_user

AWAITING = RegistrationStatus.AWAITING_UPSTREAM


@pytest.mark.django_db
def test_only_the_captain_can_withdraw(make):
    registration, captain, team, _ = make()
    mate = team.memberships.exclude(user=captain).get().user
    with pytest.raises(reg.RegistrationError, match="只有队长"):
        reg.withdraw(registration=registration, actor=mate)
    registration.refresh_from_db()
    assert registration.status == RegistrationStatus.PENDING


@pytest.mark.django_db
def test_a_local_admin_may_not_reject_what_awaits_the_upstream(make):
    """Design 8.5, two-stage mode: once passed locally, only the upstream decides."""
    registration, *_ = make(ReviewMode.TWO_STAGE, AWAITING)
    with pytest.raises(reg.RegistrationError, match="由上游操作"):
        reg.reject(registration=registration, actor=admin_user(), note="不行")
    registration.refresh_from_db()
    assert registration.status == AWAITING


@pytest.mark.django_db
def test_a_deactivated_member_blocks_the_roster_without_saying_why(make):
    """Design 8.3 check 5: the captain sees 「暂时无法参加」, not 「已停用」."""
    registration, captain, team, _ = make()
    mate = team.memberships.exclude(user=captain).get().user
    User.objects.filter(pk=mate.pk).update(is_active=False)
    mate.refresh_from_db()
    problems = reg.member_problems(tournament=registration.tournament, user=mate)
    assert f"{mate.nickname} 暂时无法参加赛事报名" in problems
    assert not any("停用" in problem for problem in problems)


@pytest.mark.django_db
def test_a_cancelled_tournament_cannot_be_published_again(make):
    registration, *_ = make()
    tournament = registration.tournament
    services.cancel(tournament=tournament, actor=admin_user(), reason="场地取消")
    with pytest.raises(services.TournamentError, match="已取消"):
        services.publish(tournament=tournament, actor=admin_user())
    tournament.refresh_from_db()
    assert tournament.status == TournamentStatus.CANCELLED


@pytest.mark.django_db
def test_a_draft_tournament_has_no_registration_page(client, make):
    registration, captain, *_ = make()
    tournament = registration.tournament
    tournament.status = TournamentStatus.DRAFT
    tournament.save(update_fields=["status"])
    client.force_login(captain)
    response = client.get(reverse("tournament_register", args=[tournament.pk]))
    assert response.status_code == 404
