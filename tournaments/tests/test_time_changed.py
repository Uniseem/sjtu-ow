"""Round 139, reworked in 201: moving a published tournament mails nobody on
saving; the time the people taking part knew is kept until someone presses
「通知报名的人」, whose letter says from when to when (design 8.1, 10.4, v7.5;
v6.34 mailed on every save that moved the time)."""

from datetime import timedelta
from unittest import mock

import pytest
from django.core import mail
from django.urls import reverse
from django.utils import timezone
from wagtail.test.utils.form_data import querydict_from_html

from accounts.models import User
from core import services as core_services
from core.models import Broadcast, SiteSettings
from tournaments import services
from tournaments.models import Tournament, TournamentStatus
from tournaments.tests.test_state_table import APPROVED


def _updates():
    return [m for m in mail.outbox if "赛事有更新" in m.subject]


def _at(tournament, delta, **extra):
    Tournament.objects.filter(pk=tournament.pk).update(
        starts_at=timezone.now() + delta, **extra
    )
    tournament.refresh_from_db()
    return tournament.starts_at


def _fmt(value):
    return f"{timezone.localtime(value):%Y-%m-%d %H:%M}"


def _admin(email="root201@example.com"):
    return User.objects.create_superuser(
        email=email,
        password="Correct-Horse-Battery-1",
        nickname=email.split("@")[0][:12],
        agreed_terms_at=timezone.now(),
        agreed_cross_border_at=timezone.now(),
    )


@pytest.fixture
def smtp(db):
    row = SiteSettings.load()
    row.smtp_host = "smtp.example.com"
    row.from_address = "noreply@example.com"
    row.save()


@pytest.fixture
def worker():
    """What announce() queues is delivered when the transaction commits."""
    task = mock.Mock()
    task.enqueue.side_effect = lambda pk: core_services.deliver(
        Broadcast.objects.get(pk=pk)
    )
    with mock.patch("core.tasks.send_broadcast", task):
        yield task


def _tell(capture, tournament, note=""):
    with capture(execute=True):
        return core_services.announce(
            kind="tournament",
            obj=tournament,
            actor=_admin(f"teller{Broadcast.objects.count()}@example.com"),
            audience="participants",
            note=note,
        )


# --- saving -----------------------------------------------------------------


@pytest.mark.django_db
def test_moving_mails_nobody_and_keeps_what_they_knew(
    make, django_capture_on_commit_callbacks
):
    registration, *_ = make(APPROVED)
    tournament = registration.tournament
    old = _at(tournament, timedelta(days=1), reminder_sent_at=timezone.now())
    _at(tournament, timedelta(days=3))
    mail.outbox.clear()
    with django_capture_on_commit_callbacks(execute=True):
        assert services.note_time_change(tournament, old)
    assert mail.outbox == []
    tournament.refresh_from_db()
    assert tournament.moved_from == old
    assert tournament.reminder_sent_at is None  # it goes out again


@pytest.mark.django_db
def test_the_first_time_is_kept_and_moving_back_forgets_it(make):
    registration, *_ = make(APPROVED)
    tournament = registration.tournament
    old = _at(tournament, timedelta(days=1))
    middle = _at(tournament, timedelta(days=2))
    services.note_time_change(tournament, old)
    _at(tournament, timedelta(days=3))
    services.note_time_change(tournament, middle)
    tournament.refresh_from_db()
    assert tournament.moved_from == old  # what they were told, not the step
    last = tournament.starts_at
    Tournament.objects.filter(pk=tournament.pk).update(starts_at=old)
    tournament.refresh_from_db()
    services.note_time_change(tournament, last)
    tournament.refresh_from_db()
    assert tournament.moved_from is None  # back to what they know


@pytest.mark.django_db
def test_nothing_noted_when_nothing_moved(make):
    registration, *_ = make(APPROVED)
    tournament = registration.tournament
    old = _at(tournament, timedelta(days=1))
    assert not services.note_time_change(tournament, old)  # same time
    assert not services.note_time_change(tournament, None)  # first set
    _at(tournament, -timedelta(hours=1))
    assert not services.note_time_change(tournament, old)  # moved into the past
    _at(tournament, timedelta(days=4), status=TournamentStatus.DRAFT)
    assert not services.note_time_change(tournament, old)  # not published
    tournament.refresh_from_db()
    assert tournament.moved_from is None


@pytest.mark.django_db
def test_saving_in_the_admin_mails_nobody_and_says_who_does_not_know(
    make, client, django_capture_on_commit_callbacks
):
    registration, *_ = make(APPROVED)
    tournament = registration.tournament
    _at(tournament, timedelta(days=1))
    client.force_login(_admin())
    url = reverse("tournaments:edit", args=[tournament.pk])
    data = querydict_from_html(client.get(url).content.decode(), form_index=0)
    later = timezone.localtime(timezone.now() + timedelta(days=5))
    data["starts_at"] = f"{later:%Y-%m-%d %H:%M}"
    mail.outbox.clear()
    with django_capture_on_commit_callbacks(execute=True):
        response = client.post(url, data)
    assert response.status_code == 302, response.content.decode()[:2000]
    assert mail.outbox == []
    page = client.get(url).content.decode()
    assert "data-time-moved" in page and "报名的人还不知道" in page
    notify = reverse("announce", args=["tournament", tournament.pk])
    assert f"{notify}?to=participants" in page


# --- 「通知报名的人」 ---------------------------------------------------------


@pytest.mark.django_db
def test_the_people_taking_part_hear_from_when_to_when(
    make, smtp, worker, django_capture_on_commit_callbacks
):
    registration, *_ = make(APPROVED)
    tournament = registration.tournament
    old = _at(tournament, timedelta(days=1))
    new = _at(tournament, timedelta(days=3))
    services.note_time_change(tournament, old)
    mail.outbox.clear()
    broadcast = _tell(django_capture_on_commit_callbacks, tournament, "改到线上了")
    letters = _updates()
    assert sorted(m.to[0] for m in letters) == sorted(
        row.user.email for row in registration.members.all()
    )
    body = letters[0].body
    assert _fmt(old) in body and _fmt(new) in body
    assert "管理员的说明：改到线上了" in body
    assert "之前已经发过" not in body  # the first one
    assert broadcast.audience == "participants" and broadcast.moved_from == old
    tournament.refresh_from_db()
    assert tournament.moved_from is None  # told now: the prompt goes


@pytest.mark.django_db
def test_the_pool_hears_too(smtp, worker, django_capture_on_commit_callbacks):
    from tournaments.tests.test_adhoc_teams import _pool, _tournament

    tournament = _tournament(title="散人杯201")
    (entry,) = _pool(tournament, 1, prefix="池201")
    mail.outbox.clear()
    _tell(django_capture_on_commit_callbacks, tournament)
    assert [m.to for m in _updates()] == [[entry.user.email]]
    assert "信息有更新" in _updates()[0].body  # nothing moved


@pytest.mark.django_db
def test_a_rejected_roster_does_not_hear(make, smtp):
    from tournaments.tests.test_state_table import REJECTED

    registration, *_ = make(REJECTED)
    tournament = registration.tournament
    with pytest.raises(core_services.AnnouncementError, match="还没有人报名"):
        core_services.announce(
            kind="tournament", obj=tournament, actor=_admin(), audience="participants"
        )
