"""Round 139: moving a tournament tells the people taking part (design 8.1, v6.34)."""

from datetime import timedelta

import pytest
from django.core import mail
from django.urls import reverse
from django.utils import timezone
from wagtail.test.utils.form_data import querydict_from_html

from tournaments import services
from tournaments.models import Tournament, TournamentStatus
from tournaments.tests.test_state_table import APPROVED


def _moved_letters():
    return [m for m in mail.outbox if "比赛时间改了" in m.subject]


def _at(tournament, delta, **extra):
    Tournament.objects.filter(pk=tournament.pk).update(
        starts_at=timezone.now() + delta, **extra
    )
    tournament.refresh_from_db()
    return tournament.starts_at


def _fmt(value):
    return f"{timezone.localtime(value):%Y-%m-%d %H:%M}"


@pytest.mark.django_db
def test_the_people_taking_part_hear_from_when_to_when(
    make, django_capture_on_commit_callbacks
):
    registration, *_ = make(APPROVED)
    tournament = registration.tournament
    old = _at(tournament, timedelta(days=1), reminder_sent_at=timezone.now())
    new = _at(tournament, timedelta(days=3))
    mail.outbox.clear()
    with django_capture_on_commit_callbacks(execute=True):
        assert services.time_changed(tournament, old)
    letters = _moved_letters()
    assert sorted(m.to[0] for m in letters) == sorted(
        row.user.email for row in registration.members.all()
    )
    assert _fmt(old) in letters[0].body and _fmt(new) in letters[0].body
    tournament.refresh_from_db()
    assert tournament.reminder_sent_at is None


@pytest.mark.django_db
def test_nothing_said_when_nothing_moved(make, django_capture_on_commit_callbacks):
    registration, *_ = make(APPROVED)
    tournament = registration.tournament
    old = _at(tournament, timedelta(days=1))
    mail.outbox.clear()
    with django_capture_on_commit_callbacks(execute=True):
        assert not services.time_changed(tournament, old)  # same time
        assert not services.time_changed(tournament, None)  # first set
        _at(tournament, -timedelta(hours=1))
        assert not services.time_changed(tournament, old)  # moved into the past
        _at(tournament, timedelta(days=4), status=TournamentStatus.DRAFT)
        assert not services.time_changed(tournament, old)  # not published
    assert _moved_letters() == []


@pytest.mark.django_db
def test_the_pool_hears_too(django_capture_on_commit_callbacks):
    from tournaments.tests.test_adhoc_teams import _pool, _tournament

    tournament = _tournament(title="散人杯139")
    (entry,) = _pool(tournament, 1, prefix="池139")
    old = _at(tournament, timedelta(days=1))
    _at(tournament, timedelta(days=2))
    mail.outbox.clear()
    with django_capture_on_commit_callbacks(execute=True):
        services.time_changed(tournament, old)
    assert [m.to for m in _moved_letters()] == [[entry.user.email]]


@pytest.mark.django_db
def test_saving_in_the_admin_sends_it(make, client, django_capture_on_commit_callbacks):
    from accounts.models import User

    registration, *_ = make(APPROVED)
    tournament = registration.tournament
    _at(tournament, timedelta(days=1))
    admin = User.objects.create_superuser(
        email="root139@example.com",
        password="Correct-Horse-Battery-1",
        nickname="站长139",
        agreed_terms_at=timezone.now(),
        agreed_cross_border_at=timezone.now(),
    )
    client.force_login(admin)
    url = reverse("tournaments:edit", args=[tournament.pk])
    data = querydict_from_html(
        client.get(url).content.decode(), form_id="w-editor-form"
    )
    later = timezone.localtime(timezone.now() + timedelta(days=5))
    data["starts_at"] = f"{later:%Y-%m-%d %H:%M}"
    mail.outbox.clear()
    with django_capture_on_commit_callbacks(execute=True):
        response = client.post(url, data)
    assert response.status_code == 302, response.content.decode()[:2000]
    assert len(_moved_letters()) == registration.members.count()


@pytest.mark.django_db
def test_a_rejected_roster_does_not_hear(make, django_capture_on_commit_callbacks):
    from tournaments.tests.test_state_table import REJECTED

    registration, *_ = make(REJECTED)
    tournament = registration.tournament
    old = _at(tournament, timedelta(days=1))
    _at(tournament, timedelta(days=2))
    mail.outbox.clear()
    with django_capture_on_commit_callbacks(execute=True):
        services.time_changed(tournament, old)
    assert _moved_letters() == []
