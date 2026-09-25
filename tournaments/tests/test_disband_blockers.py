"""Design 7.5: a team with a live registration cannot be disbanded (round 061).

Until round 061 disband_blockers() returned an empty list, with a comment
saying M4 would add the check. M4 never came back to it.
"""

import pytest

from teams import services as team_services
from tournaments import registration as reg
from tournaments.models import (
    Registration,
    RegistrationStatus,
    Tournament,
    TournamentStatus,
)
from tournaments.tests.test_state_table import _force, admin_user


@pytest.mark.django_db
@pytest.mark.parametrize(
    "status",
    [
        RegistrationStatus.PENDING,
        RegistrationStatus.APPROVED,
    ],
)
def test_a_live_registration_stops_the_captain(make, status):
    registration, captain, team, _ = make(status)
    with pytest.raises(team_services.TeamError, match=registration.tournament.title):
        team_services.disband_team(team=team, actor=captain)
    team.refresh_from_db()
    assert not team.is_disbanded


@pytest.mark.django_db
def test_it_stops_a_superuser_too(make):
    registration, _captain, team, _ = make()
    root = admin_user("disband-root@example.com")
    root.is_superuser = True
    root.save(update_fields=["is_superuser"])
    with pytest.raises(team_services.TeamError, match="请先撤回报名"):
        team_services.disband_team(team=team, actor=root)


@pytest.mark.django_db
def test_a_draft_tournament_still_counts(make):
    registration, captain, team, _ = make()
    Tournament.objects.filter(pk=registration.tournament_id).update(
        status=TournamentStatus.DRAFT
    )
    with pytest.raises(team_services.TeamError):
        team_services.disband_team(team=team, actor=captain)


@pytest.mark.django_db
@pytest.mark.parametrize(
    "status", [RegistrationStatus.REJECTED, RegistrationStatus.WITHDRAWN]
)
def test_a_closed_registration_does_not(make, status):
    registration, captain, team, _ = make()
    _force(registration, status)
    team_services.disband_team(team=team, actor=captain)
    team.refresh_from_db()
    assert team.is_disbanded


@pytest.mark.django_db
@pytest.mark.parametrize(
    "tournament_status", [TournamentStatus.FINISHED, TournamentStatus.CANCELLED]
)
def test_a_finished_or_cancelled_tournament_does_not(make, tournament_status):
    registration, captain, team, _ = make()
    _force(registration, RegistrationStatus.APPROVED)
    Tournament.objects.filter(pk=registration.tournament_id).update(
        status=tournament_status
    )
    team_services.disband_team(team=team, actor=captain)
    team.refresh_from_db()
    assert team.is_disbanded


@pytest.mark.django_db
def test_withdrawing_first_lets_the_captain_disband(make):
    registration, captain, team, _ = make()
    reg.withdraw(registration=registration, actor=captain)
    team_services.disband_team(team=team, actor=captain)
    team.refresh_from_db()
    assert team.is_disbanded
    assert Registration.objects.filter(pk=registration.pk).exists()


@pytest.mark.django_db
def test_every_blocking_tournament_is_named(make):
    first, captain, team, selections = make()
    second_tournament = Tournament.objects.create(
        title="第二个赛事",
        registration_opens_at=first.tournament.registration_opens_at,
        registration_closes_at=first.tournament.registration_closes_at,
        roster_min=2,
        roster_max=3,
        status=TournamentStatus.PUBLISHED,
        published_at=first.tournament.published_at,
    )
    reg.submit(
        tournament=second_tournament, team=team, actor=captain, selections=selections
    )
    blockers = team_services.disband_blockers(team)
    assert len(blockers) == 2
    assert any("第二个赛事" in reason for reason in blockers)
