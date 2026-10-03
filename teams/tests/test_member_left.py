"""Round 131: the captain hears when someone leaves (design 7.4, v6.26)."""

import pytest
from django.core import mail

from teams import services as team_services
from tournaments.models import Registration, Tournament, TournamentStatus
from tournaments.tests.test_state_table import (  # noqa: F401 (make is a fixture)
    APPROVED,
    PENDING,
    REJECTED,
    make,
    player,
)


def _left_letters():
    return [message for message in mail.outbox if "队员退出战队" in message.subject]


@pytest.mark.django_db
def test_the_captain_hears_who_left():
    captain = player("cap131@example.com", "队长131")
    mate = player("mate131@example.com", "队员131")
    team = team_services.create_team(user=captain, name="退出测试队")
    application = team_services.apply_to_team(
        team=team, user=mate, roles={"tank": True}
    )
    team_services.approve_application(application=application, actor=captain)
    mail.outbox.clear()

    team_services.leave_team(team=team, user=mate)

    letters = _left_letters()
    assert [message.to for message in letters] == [[captain.email]]
    assert letters[0].subject.endswith("队员退出战队：退出测试队")
    assert "队员131" in letters[0].body
    assert f"/teams/{team.pk}/manage/" in letters[0].body
    assert "报名名单" not in letters[0].body


@pytest.mark.django_db
@pytest.mark.parametrize("status", [PENDING, APPROVED])
def test_a_live_roster_that_still_lists_them_is_named(make, status):  # noqa: F811
    registration, captain, team, _selections = make(status)
    mate = registration.members.exclude(user=captain).get().user
    mail.outbox.clear()

    team_services.leave_team(team=team, user=mate)

    body = _left_letters()[0].body
    assert registration.tournament.title in body
    assert "同步名单" in body
    assert registration.get_absolute_url() in body


@pytest.mark.django_db
def test_dead_registrations_are_not_named(make):  # noqa: F811
    rejected, captain, team, _selections = make(REJECTED)
    mate = rejected.members.exclude(user=captain).get().user
    finished, *_ = make(APPROVED)
    Tournament.objects.filter(pk=finished.tournament.pk).update(
        status=TournamentStatus.FINISHED
    )
    # The same team on a finished tournament, with the same mate listed.
    Registration.objects.filter(pk=finished.pk).update(team=team)
    finished.members.filter(is_captain=False).update(user=mate)
    mail.outbox.clear()

    team_services.leave_team(team=team, user=mate)

    body = _left_letters()[0].body
    assert rejected.tournament.title not in body
    assert finished.tournament.title not in body
    assert "同步名单" not in body


def test_the_letter_is_on_the_specimen_page():
    from core.email_samples import sample

    found = sample("member-left")
    assert found is not None
    assert "同步名单" in found.text
