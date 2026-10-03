"""Round 137: a contact for the people taking part only (design 8.1, v6.32)."""

from datetime import timedelta

import pytest
from django.urls import reverse
from django.utils import timezone

from tournaments import registration as reg
from tournaments.models import Tournament
from tournaments.notifications import (
    tournament_reminder_letter,
    unplaced_reminder_letter,
)
from tournaments.notifications_registration import (
    adhoc_team_formed_letter,
    registration_status_changed_letter,
    team_member_entered_letter,
)
from tournaments.tests.test_state_table import APPROVED, PENDING, REJECTED, player

GROUP = "选手群 987654321"


def _with_contact(tournament):
    Tournament.objects.filter(pk=tournament.pk).update(participant_contact=GROUP)
    tournament.refresh_from_db()
    return tournament


def _slot(client, tournament):
    return client.get(
        reverse("state_fragment"), {"slots": f"tournament-actions:{tournament.pk}"}
    ).content.decode()


@pytest.mark.django_db
def test_who_takes_part(make):
    pending, captain, *_ = make(PENDING)
    mate = pending.members.exclude(user=captain).get().user
    assert reg.takes_part(pending.tournament, captain)
    assert reg.takes_part(pending.tournament, mate)
    assert not reg.takes_part(pending.tournament, player("x137@example.com", "路人137"))
    rejected, rejected_captain, *_ = make(REJECTED)
    assert not reg.takes_part(rejected.tournament, rejected_captain)


@pytest.mark.django_db
def test_the_tournament_page_shows_it_to_participants_only(make, client):
    registration, captain, *_ = make(APPROVED)
    tournament = _with_contact(registration.tournament)
    mate = registration.members.exclude(user=captain).get().user
    for person in (captain, mate):
        client.force_login(person)
        assert GROUP in _slot(client, tournament)
    client.force_login(player("y137@example.com", "路人137b"))
    assert GROUP not in _slot(client, tournament)
    client.logout()
    assert GROUP not in _slot(client, tournament)
    assert GROUP not in client.get(tournament.get_absolute_url()).content.decode()


@pytest.mark.django_db
def test_the_pool_sees_it_too(client):
    from tournaments.tests.test_adhoc_teams import _pool, _tournament

    tournament = _with_contact(_tournament(title="散人杯137"))
    (entry,) = _pool(tournament, 1, prefix="池137")
    client.force_login(entry.user)
    assert GROUP in _slot(client, tournament)


@pytest.mark.django_db
def test_the_registration_page_shows_it_while_live(make, client):
    registration, captain, *_ = make(APPROVED)
    _with_contact(registration.tournament)
    client.force_login(captain)
    url = registration.get_absolute_url()
    assert GROUP in client.get(url).content.decode()
    rejected, rejected_captain, *_ = make(REJECTED)
    _with_contact(rejected.tournament)
    client.force_login(rejected_captain)
    assert GROUP not in client.get(rejected.get_absolute_url()).content.decode()


@pytest.mark.django_db
def test_the_letters_to_participants_carry_it(make):
    registration, captain, *_ = make(APPROVED)
    tournament = _with_contact(registration.tournament)
    registration.refresh_from_db()
    row = registration.members.get(user=captain)
    Tournament.objects.filter(pk=tournament.pk).update(
        starts_at=timezone.now() + timedelta(days=1)
    )
    tournament.refresh_from_db()
    registration.refresh_from_db()
    fact = ("选手联系方式", GROUP)
    assert fact in registration_status_changed_letter(registration).facts
    assert fact in team_member_entered_letter(registration, row).facts
    assert fact in adhoc_team_formed_letter(registration).facts
    assert fact in tournament_reminder_letter(tournament, row).facts
    assert fact in unplaced_reminder_letter(tournament).facts

    rejected, *_ = make(REJECTED)
    _with_contact(rejected.tournament)
    rejected.refresh_from_db()
    assert fact not in registration_status_changed_letter(rejected).facts


@pytest.mark.django_db
def test_the_admin_form_has_it(client):
    from accounts.models import User

    call = User.objects.create_superuser(
        email="root137@example.com",
        password="Correct-Horse-Battery-1",
        nickname="站长137",
        agreed_terms_at=timezone.now(),
        agreed_cross_border_at=timezone.now(),
    )
    client.force_login(call)
    html = client.get(reverse("tournaments:add")).content.decode()
    assert 'name="participant_contact"' in html
