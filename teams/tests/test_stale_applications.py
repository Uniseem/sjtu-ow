"""Round 141: applications nobody answered close after 14 days (design 7.3, v6.36)."""

from datetime import timedelta
from io import StringIO

import pytest
from django.core import mail
from django.core.management import call_command
from django.utils import timezone

from teams import services as team_services
from teams.models import ApplicationStatus, TeamApplication
from tournaments.tests.test_state_table import player


def _application(team, email, nickname, days_ago):
    applicant = player(email, nickname)
    application = team_services.apply_to_team(
        team=team, user=applicant, roles={"support": True}
    )
    TeamApplication.objects.filter(pk=application.pk).update(
        created_at=timezone.now() - timedelta(days=days_ago)
    )
    return application


@pytest.fixture
def team(db):
    captain = player("cap141@example.com", "队长141")
    return team_services.create_team(user=captain, name="不在线的队")


def _closed_letters():
    return [m for m in mail.outbox if "入队申请已关闭" in m.subject]


@pytest.mark.django_db
def test_two_weeks_unanswered_closes_and_tells_the_applicant(team):
    old = _application(team, "old141@example.com", "等太久", 15)
    fresh = _application(team, "new141@example.com", "刚申请", 13)
    mail.outbox.clear()
    out = StringIO()
    call_command("cleanup_old_data", stdout=out)
    old.refresh_from_db()
    fresh.refresh_from_db()
    assert old.status == ApplicationStatus.CANCELLED
    assert old.decision_note == team_services.STALE_NOTE
    assert fresh.status == ApplicationStatus.PENDING
    assert [m.to for m in _closed_letters()] == [[old.applicant.email]]
    assert "/teams/?recruiting=1" in _closed_letters()[0].body
    assert "已关闭 14 天没人处理的入队申请（并通知申请人）：1" in out.getvalue()
    # They may knock again.
    team_services.apply_to_team(team=team, user=old.applicant, roles={"tank": True})


@pytest.mark.django_db
def test_answered_ones_are_left_alone(team):
    done = _application(team, "done141@example.com", "早处理了", 0)
    team_services.reject_application(
        application=done, actor=team.captain(), note="位置满了"
    )
    # Saving the decision writes every field, so age it afterwards.
    TeamApplication.objects.filter(pk=done.pk).update(
        created_at=timezone.now() - timedelta(days=30)
    )
    mail.outbox.clear()
    call_command("cleanup_old_data", stdout=StringIO())
    done.refresh_from_db()
    assert done.status == ApplicationStatus.REJECTED
    assert done.decision_note == "位置满了"
    assert _closed_letters() == []


@pytest.mark.django_db
def test_a_dry_run_only_counts(team):
    old = _application(team, "dry141@example.com", "试运行", 20)
    mail.outbox.clear()
    out = StringIO()
    call_command("cleanup_old_data", "--dry-run", stdout=out)
    old.refresh_from_db()
    assert old.status == ApplicationStatus.PENDING
    assert _closed_letters() == []
    assert "将关闭 14 天没人处理的入队申请（并通知申请人）：1" in out.getvalue()


# --- a week in, the captain hears (round 145, design 7.3 v6.39) --------------------


def _waiting_letters():
    return [m for m in mail.outbox if "入队申请等你处理" in m.subject]


@pytest.mark.django_db
def test_a_week_in_the_captain_hears_once(team):
    first = _application(team, "w1145@example.com", "等一周甲", 8)
    second = _application(team, "w2145@example.com", "等一周乙", 9)
    _application(team, "w3145@example.com", "刚三天", 3)
    mail.outbox.clear()
    out = StringIO()
    call_command("cleanup_old_data", stdout=out)
    (letter,) = _waiting_letters()
    assert letter.to == [team.captain().email]
    assert "等一周甲" in letter.body and "等一周乙" in letter.body
    assert "刚三天" not in letter.body
    assert "再过 7 天没处理会自动关闭" in letter.body
    assert "已提醒队长（入队申请等了 7 天）：1 封" in out.getvalue()
    first.refresh_from_db()
    second.refresh_from_db()
    assert first.captain_reminded_at and second.captain_reminded_at
    mail.outbox.clear()
    call_command("cleanup_old_data", stdout=StringIO())
    assert _waiting_letters() == []


@pytest.mark.django_db
def test_two_weeks_in_it_just_closes(team):
    _application(team, "late145@example.com", "太晚了", 15)
    mail.outbox.clear()
    call_command("cleanup_old_data", stdout=StringIO())
    assert _waiting_letters() == []
    assert len(_closed_letters()) == 1


def test_the_reminder_is_on_the_specimen_page():
    from core.email_samples import sample

    assert "自动关闭" in sample("applications-waiting").text
