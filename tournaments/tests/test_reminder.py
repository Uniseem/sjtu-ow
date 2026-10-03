"""Round 129: players hear a day before the match starts (design 8.1, v6.24)."""

from datetime import timedelta
from unittest import mock

import pytest
from django.core import mail
from django.utils import timezone

from core.models import SiteSettings
from tournaments import services
from tournaments.models import Tournament, TournamentStatus
from tournaments.notifications_registration import registration_status_changed_letter
from tournaments.tasks import send_tournament_reminder
from tournaments.tests.test_state_table import APPROVED, PENDING, REJECTED


def _starts_in(tournament, delta):
    Tournament.objects.filter(pk=tournament.pk).update(starts_at=timezone.now() + delta)
    tournament.refresh_from_db()


def _reminders():
    """Building a roster mails people too (applications and the like)."""
    return [message for message in mail.outbox if "赛事提醒" in message.subject]


def _arranged(tournament, django_capture_on_commit_callbacks):
    with mock.patch("tournaments.tasks.send_tournament_reminder") as task:
        with django_capture_on_commit_callbacks(execute=True):
            services.publish(tournament=tournament, actor=None)
    return task


@pytest.mark.django_db
def test_publishing_arranges_it_a_day_before(django_capture_on_commit_callbacks):
    starts = timezone.now() + timedelta(days=3)
    tournament = Tournament.objects.create(
        title="提醒杯",
        starts_at=starts,
        registration_opens_at=timezone.now() - timedelta(days=1),
        registration_closes_at=timezone.now() + timedelta(days=2),
    )
    task = _arranged(tournament, django_capture_on_commit_callbacks)
    task.using.assert_called_once_with(run_after=starts - timedelta(hours=24))
    task.using.return_value.enqueue.assert_called_once_with(tournament.pk)

    settings = SiteSettings.load()
    settings.tournament_reminder_hours = 6
    settings.save()
    task = _arranged(tournament, django_capture_on_commit_callbacks)
    task.using.assert_called_once_with(run_after=starts - timedelta(hours=6))


@pytest.mark.django_db
def test_no_start_time_no_reminder(django_capture_on_commit_callbacks):
    tournament = Tournament.objects.create(
        title="没定时间杯",
        registration_opens_at=timezone.now() - timedelta(days=1),
        registration_closes_at=timezone.now() + timedelta(days=2),
    )
    task = _arranged(tournament, django_capture_on_commit_callbacks)
    task.using.assert_not_called()
    task.enqueue.assert_not_called()
    assert send_tournament_reminder.func(tournament.pk) == "no_start"


@pytest.mark.django_db
def test_each_approved_player_gets_their_own(make):
    registration, captain, team, _selections = make(APPROVED)
    tournament = registration.tournament
    _starts_in(tournament, timedelta(hours=3))

    assert send_tournament_reminder.func(tournament.pk) == "sent:2"
    letters = {message.to[0]: message for message in _reminders()}
    assert set(letters) == {row.user.email for row in registration.members.all()}
    for row in registration.members.all():
        letter = letters[row.user.email]
        assert letter.subject.endswith(f"赛事提醒：{tournament.title}")
        assert registration.team_name in letter.body
        assert row.battletag in letter.body
        assert f"{timezone.localtime(tournament.starts_at):%Y-%m-%d %H:%M}" in (
            letter.body
        )
    others = [row.battletag for row in registration.members.exclude(user=captain)]
    assert others[0] not in letters[captain.email].body

    assert send_tournament_reminder.func(tournament.pk) == "already_sent"
    assert len(_reminders()) == 2


@pytest.mark.django_db
def test_only_approved_rosters_hear(make):
    for status in (PENDING, REJECTED):
        registration, *_ = make(status)
        tournament = registration.tournament
        _starts_in(tournament, timedelta(hours=3))
        assert send_tournament_reminder.func(tournament.pk) == "sent:0"
        tournament.refresh_from_db()
        assert tournament.reminder_sent_at is None
    assert _reminders() == []


@pytest.mark.django_db
def test_players_who_left_or_were_deactivated_are_skipped(make):
    registration, captain, team, _selections = make(APPROVED)
    tournament = registration.tournament
    mate = registration.members.exclude(user=captain).get()
    registration.members.filter(pk=mate.pk).update(is_active=False)
    _starts_in(tournament, timedelta(hours=3))
    assert send_tournament_reminder.func(tournament.pk) == "sent:1"
    assert [message.to for message in _reminders()] == [[captain.email]]

    other, captain2, *_ = make(APPROVED)
    captain2.is_active = False
    captain2.save(update_fields=["is_active"])
    _starts_in(other.tournament, timedelta(hours=3))
    assert send_tournament_reminder.func(other.tournament.pk) == "sent:1"


@pytest.mark.django_db
def test_a_later_start_or_a_cancellation_holds_it(make):
    registration, *_ = make(APPROVED)
    tournament = registration.tournament
    _starts_in(tournament, timedelta(days=5))
    with mock.patch("tournaments.tasks.send_tournament_reminder") as task:
        assert send_tournament_reminder.func(tournament.pk) == "rescheduled"
    task.using.assert_called_once_with(
        run_after=tournament.starts_at - timedelta(hours=24)
    )
    _starts_in(tournament, timedelta(hours=3))
    Tournament.objects.filter(pk=tournament.pk).update(
        status=TournamentStatus.CANCELLED
    )
    assert send_tournament_reminder.func(tournament.pk) == "not_published"
    assert _reminders() == []


@pytest.mark.django_db
def test_the_approval_says_when_to_show_up(make):
    registration, *_ = make(APPROVED)
    _starts_in(registration.tournament, timedelta(days=2))
    registration.refresh_from_db()
    when = f"{timezone.localtime(registration.tournament.starts_at):%Y-%m-%d %H:%M}"
    approved = registration_status_changed_letter(registration)
    assert ("比赛时间", when) in approved.facts
    rejected, *_ = make(REJECTED)
    _starts_in(rejected.tournament, timedelta(days=2))
    rejected.refresh_from_db()
    assert "比赛时间" not in dict(registration_status_changed_letter(rejected).facts)


def test_the_reminder_is_on_the_specimen_page():
    from core.email_samples import sample

    found = sample("tournament-reminder")
    assert found is not None
    assert "你的游戏 ID" in found.text
    assert "比赛时间" in sample("approved").text


# --- the pool (round 134, design 8.1 v6.29) -------------------------------------


def _individual_cup(django_capture_on_commit_callbacks, *, form=True):
    from tournaments import registration as reg
    from tournaments.tests.test_adhoc_teams import _admin, _layout, _pool, _tournament

    tournament = _tournament(title="散人杯134")
    entries = _pool(tournament, 3, prefix="散134")
    if form:
        with django_capture_on_commit_callbacks(execute=True):
            reg.form_teams(
                tournament=tournament,
                actor=_admin(),
                layout=_layout(("一队", entries[:2])),
            )
    _starts_in(tournament, timedelta(hours=3))
    return tournament, entries


@pytest.mark.django_db
def test_the_pool_hears_once_teams_are_being_formed(django_capture_on_commit_callbacks):
    tournament, entries = _individual_cup(django_capture_on_commit_callbacks)
    mail.outbox.clear()
    assert send_tournament_reminder.func(tournament.pk) == "sent:2,pool:1"
    letters = {message.to[0]: message.body for message in _reminders()}
    left_out = entries[2].user.email
    assert "没有被编进队伍" in letters.pop(left_out)
    assert all("一队" in body for body in letters.values())


@pytest.mark.django_db
def test_no_teams_yet_no_pool_letters(django_capture_on_commit_callbacks):
    tournament, _entries = _individual_cup(
        django_capture_on_commit_callbacks, form=False
    )
    mail.outbox.clear()
    assert send_tournament_reminder.func(tournament.pk) == "sent:0"
    assert _reminders() == []
    tournament.refresh_from_db()
    assert tournament.reminder_sent_at is None


@pytest.mark.django_db
def test_being_placed_says_when(django_capture_on_commit_callbacks):
    tournament, entries = _individual_cup(django_capture_on_commit_callbacks)
    formed = [m for m in mail.outbox if "已编入临时队伍" in m.subject]
    assert formed
    assert "比赛时间" not in formed[0].body  # no start time when they were placed
    from tournaments.notifications_registration import adhoc_team_formed_letter

    registration = tournament.registrations.get()
    when = f"{timezone.localtime(tournament.starts_at):%Y-%m-%d %H:%M}"
    assert ("比赛时间", when) in adhoc_team_formed_letter(registration).facts


def test_the_pool_letter_is_on_the_specimen_page():
    from core.email_samples import sample

    assert "散人池" in sample("unplaced-reminder").text


@pytest.mark.django_db
def test_a_deactivated_pool_signup_is_skipped(django_capture_on_commit_callbacks):
    tournament, entries = _individual_cup(django_capture_on_commit_callbacks)
    left_out = entries[2].user
    left_out.is_active = False
    left_out.save(update_fields=["is_active"])
    assert send_tournament_reminder.func(tournament.pk) == "sent:2"
