"""Design 3.8: deleting an account, and downloading your own data."""

import json
from datetime import timedelta

import pytest
from allauth.account.models import EmailAddress
from django.contrib.auth.models import Group
from django.urls import reverse
from django.utils import timezone

from accounts.models import ContactMethod, FeatureUserRule, User
from accounts.services import (
    DELETED_NICKNAME,
    AccountDeletionError,
    delete_account,
)
from scrims.models import Scrim
from scrims.tests.test_scrims import make_scrim
from teams import services as team_services
from teams.models import ApplicationStatus
from tournaments import registration as reg
from tournaments.models import RegistrationMember, Tournament, TournamentStatus
from tournaments.tests.test_state_table import player

PASSWORD = "Correct-Horse-Battery-1"


@pytest.fixture
def world(db):
    """A member of a team, in a submitted roster, signed up and placed in a scrim."""
    captain = player("captain@example.com", "队长")
    ContactMethod.objects.filter(user=captain).update(value="999999999")
    member = player("member@example.com", "要注销的人")
    team = team_services.create_team(user=captain, name="注销测试队")
    application = team_services.apply_to_team(
        team=team, user=member, roles={"damage": True}
    )
    team_services.approve_application(application=application, actor=captain)

    now = timezone.now()
    tournament = Tournament.objects.create(
        title="注销测试赛",
        registration_opens_at=now - timedelta(days=1),
        registration_closes_at=now + timedelta(days=7),
        roster_min=2,
        roster_max=3,
        status=TournamentStatus.PUBLISHED,
        published_at=now,
    )
    selections = {
        str(m.user.pk): m.user.game_accounts.first().pk for m in team.memberships.all()
    }
    reg.submit(tournament=tournament, team=team, actor=captain, selections=selections)

    other_captain = player("other@example.com", "别队队长")
    other_team = team_services.create_team(user=other_captain, name="另一支队")
    pending = team_services.apply_to_team(
        team=other_team, user=member, roles={"tank": True}
    )

    scrim = make_scrim()
    signup = scrim.signups.create(
        user=member,
        game_account=member.game_accounts.first(),
        role_damage=True,
        is_selected=True,
    )
    assert signup.is_selected

    member.groups.add(Group.objects.create(name="观察名单"))
    FeatureUserRule.objects.create(user=member, feature="team_create", allowed=False)
    EmailAddress.objects.create(user=member, email=member.email, verified=True)
    return {
        "captain": captain,
        "member": member,
        "team": team,
        "pending": pending,
        "scrim": scrim,
        "tournament": tournament,
    }


# --- what deletion does -------------------------------------------------------


@pytest.mark.django_db
def test_deleting_anonymises_the_account(world):
    member = world["member"]
    delete_account(member)
    member.refresh_from_db()

    assert member.email == f"deleted-{member.pk}@deleted.invalid"
    assert member.nickname == DELETED_NICKNAME
    assert member.is_sjtu is False
    assert member.is_active is False
    assert member.has_usable_password() is False
    assert member.deactivation_note == "用户自行注销"
    assert not EmailAddress.objects.filter(user=member).exists()


@pytest.mark.django_db
def test_deleting_removes_game_ids_contacts_groups_and_rules(world):
    member = world["member"]
    delete_account(member)

    assert not member.game_accounts.exists()
    assert not member.contact_methods.exists()
    assert not member.groups.exists()
    assert not FeatureUserRule.objects.filter(user=member).exists()


@pytest.mark.django_db
def test_deleting_drops_the_review_queues_copies_of_the_nickname(world, settings):
    from moderation.models import ModerationItem, TargetType

    member = world["member"]
    ModerationItem.objects.create(
        target_type=TargetType.NICKNAME,
        target_id=member.pk,
        field="nickname",
        excerpt="要注销的人",
        text_hash="x",
    )
    delete_account(member)
    assert not ModerationItem.objects.filter(
        target_type=TargetType.NICKNAME, target_id=member.pk
    ).exists()


@pytest.mark.django_db
def test_deleting_leaves_teams_and_cancels_applications(world):
    member = world["member"]
    delete_account(member)

    assert not member.team_memberships.exists()
    world["pending"].refresh_from_db()
    assert world["pending"].status == ApplicationStatus.CANCELLED


@pytest.mark.django_db
def test_deleting_drops_scrim_signups_and_flags_the_split(world):
    member = world["member"]
    delete_account(member)

    assert not member.scrim_signups.exists()
    assert Scrim.objects.get(pk=world["scrim"].pk).roster_changed_at is not None


@pytest.mark.django_db
def test_the_roster_snapshot_is_kept(world):
    """Design 3.8, 8.3: the roster records what was submitted."""
    member = world["member"]
    delete_account(member)

    row = RegistrationMember.objects.get(user=member)
    assert row.nickname == "要注销的人"
    assert row.battletag == "要注销的人#7000"
    assert row.game_account is None


@pytest.mark.django_db
def test_a_captain_must_hand_over_first(world):
    with pytest.raises(AccountDeletionError, match="注销测试队"):
        delete_account(world["captain"])
    world["captain"].refresh_from_db()
    assert world["captain"].is_active


@pytest.mark.django_db
def test_the_email_can_register_again(world):
    delete_account(world["member"])
    again = User.objects.create_user(
        email="member@example.com",
        password=PASSWORD,
        nickname="新账号",
        agreed_terms_at=timezone.now(),
        agreed_cross_border_at=timezone.now(),
    )
    assert again.pk != world["member"].pk


# --- the pages --------------------------------------------------------------------


@pytest.mark.django_db
def test_the_page_needs_the_current_password(client, world):
    member = world["member"]
    client.force_login(member)
    response = client.post(reverse("me_delete"), {"password": "wrong"})
    assert response.status_code == 200
    member.refresh_from_db()
    assert member.is_active


@pytest.mark.django_db
def test_deleting_logs_out_everywhere(client, world):
    from django.test import Client

    member = world["member"]
    elsewhere = Client()
    elsewhere.force_login(member)
    client.force_login(member)

    response = client.post(reverse("me_delete"), {"password": PASSWORD})

    assert response.status_code == 302
    # Being inactive already locks the account out; logging out also empties
    # the session instead of leaving the user id in it.
    assert "_auth_user_id" not in client.session
    assert client.get(reverse("me_profile")).status_code == 302
    assert elsewhere.get(reverse("me_profile")).status_code == 302


@pytest.mark.django_db
def test_a_captain_sees_why_and_gets_no_form(client, world):
    client.force_login(world["captain"])
    html = client.get(reverse("me_delete")).content.decode("utf-8")
    assert "data-deletion-blocked" in html
    assert "注销测试队" in html
    assert 'name="password"' not in html


# --- export -----------------------------------------------------------------------


@pytest.mark.django_db
def test_export_has_your_data_and_nobody_elses(client, world):
    member = world["member"]
    client.force_login(member)

    response = client.get(reverse("me_export"))

    assert response.status_code == 200
    assert "attachment" in response["Content-Disposition"]
    data = json.loads(response.content)
    assert data["account"]["email"] == "member@example.com"
    assert data["game_accounts"][0]["battletag"] == "要注销的人#7000"
    assert data["contact_methods"][0]["value"] == "123456789"
    assert {row["team"] for row in data["teams"]} == {"注销测试队"}
    assert data["tournament_registrations"][0]["tournament"] == "注销测试赛"
    assert data["scrim_signups"][0]["scrim"] == world["scrim"].title
    text = response.content.decode("utf-8")
    assert "999999999" not in text  # the captain's contact
    assert "password" not in text


@pytest.mark.django_db
def test_export_is_rate_limited(client, world):
    client.force_login(world["member"])
    for _ in range(5):
        assert client.get(reverse("me_export")).status_code == 200
    assert client.get(reverse("me_export")).status_code == 302
