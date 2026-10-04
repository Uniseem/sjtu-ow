"""Round 173: a disabled account's team application cannot be approved, and
nothing about it reaches the captain or a dead address.

Deleting the account already withdrew pending applications (leave_all_teams);
an admin disabling an account in the user admin did not, and a captain could
then approve the disabled person into the team.
"""

import pytest
from django.core import mail
from django.utils import timezone

from accounts import services
from accounts.tests.test_export_coverage import _columns_pointing_at_people
from teams import services as team_services
from teams.models import ApplicationStatus, TeamApplication, TeamMembership


@pytest.fixture
def waiting(db):
    from core.tests.test_chapter15_audit import _verified, make_user

    captain = _verified(make_user(1))
    applicant = _verified(make_user(2))
    team = team_services.create_team(user=captain, name="等人队173")
    application = team_services.apply_to_team(
        team=team, user=applicant, roles={"tank": True}, message="想来"
    )
    return captain, applicant, team, application


def test_every_column_pointing_at_a_person_has_a_fate_on_deletion(db):
    assert _columns_pointing_at_people() == set(services.ON_DELETION)


@pytest.mark.django_db
def test_deleting_the_account_closes_what_was_waiting(waiting):
    captain, applicant, team, application = waiting
    services.delete_account(applicant)
    application.refresh_from_db()
    assert application.status == ApplicationStatus.CANCELLED
    assert list(team_services.pending_applications(team)) == []


@pytest.mark.django_db
def test_a_disabled_applicant_cannot_be_approved(waiting):
    captain, applicant, team, application = waiting
    applicant.is_active = False
    applicant.save(update_fields=["is_active"])
    assert list(team_services.pending_applications(team)) == []
    with pytest.raises(team_services.TeamError, match="注销或停用"):
        team_services.approve_application(application=application, actor=captain)
    application.refresh_from_db()
    assert application.status == ApplicationStatus.CANCELLED  # closed, not left
    assert not TeamMembership.objects.filter(team=team, user=applicant).exists()


@pytest.mark.django_db
def test_no_reminder_or_letter_about_them(waiting, mailoutbox):
    captain, applicant, team, application = waiting
    mailoutbox.clear()  # the captain's 「新的入队申请」
    applicant.is_active = False
    applicant.save(update_fields=["is_active"])
    old = timezone.now() - timezone.timedelta(days=20)
    TeamApplication.objects.filter(pk=application.pk).update(created_at=old)
    assert team_services.remind_captains() == 0
    assert team_services.close_stale_applications() == 1
    assert mailoutbox == []


def test_no_letter_goes_to_a_deleted_address():
    from core.letters import people

    class Person:
        def __init__(self, email):
            self.email, self.nickname = email, "人"

    found = people([Person("deleted-7@deleted.invalid"), Person("ok@example.com")])
    assert [address for address, _name in found] == ["ok@example.com"]
    assert mail.outbox == []
