"""Round 136: a way to reach the team, for its members only (design 7.1, v6.31)."""

import pytest
from django.core import mail
from django.urls import reverse

from teams import services as team_services
from teams.forms import TeamForm
from teams.models import Team
from tournaments.tests.test_state_table import player

GROUP = "QQ 群 123456789"


def _team():
    captain = player("cap136@example.com", "队长136")
    team = team_services.create_team(user=captain, name="联系测试队")
    return team, captain


def _join(team, captain, email, nickname):
    mate = player(email, nickname)
    application = team_services.apply_to_team(
        team=team, user=mate, roles={"tank": True}
    )
    team_services.approve_application(application=application, actor=captain)
    return mate


def _slot(client, team):
    return client.get(
        reverse("state_fragment"), {"slots": f"team-join:{team.pk}"}
    ).content.decode()


@pytest.mark.django_db
def test_the_captain_sets_it_on_the_manage_page(client):
    team, captain = _team()
    client.force_login(captain)
    manage = reverse("team_manage", args=[team.pk])
    assert 'name="member_contact"' in client.get(manage).content.decode()
    response = client.post(
        manage,
        {
            "form": "profile",
            "name": team.name,
            "description": "",
            "is_recruiting": "on",
            "member_contact": f"  {GROUP}  ",
        },
    )
    assert response.status_code == 302
    assert Team.objects.get(pk=team.pk).member_contact == GROUP
    assert "member_contact" not in TeamForm().fields


@pytest.mark.django_db
def test_only_members_see_it(client):
    team, captain = _team()
    Team.objects.filter(pk=team.pk).update(member_contact=GROUP)
    mate = _join(team, captain, "mate136@example.com", "队员136")

    client.force_login(mate)
    assert GROUP in _slot(client, team)
    assert GROUP in client.get(team.get_absolute_url()).content.decode()
    client.force_login(captain)
    assert GROUP in _slot(client, team)

    client.force_login(player("out136@example.com", "路人136"))
    assert GROUP not in _slot(client, team)
    assert GROUP not in client.get(team.get_absolute_url()).content.decode()
    client.logout()
    assert GROUP not in client.get(team.get_absolute_url()).content.decode()
    assert GROUP not in _slot(client, team)


@pytest.mark.django_db
def test_the_captain_is_nudged_to_fill_it(client):
    team, captain = _team()
    client.force_login(captain)
    assert "还没填队内联系方式" in _slot(client, team)
    mate = _join(team, captain, "mate136b@example.com", "队员136b")
    client.force_login(mate)
    assert "还没填队内联系方式" not in _slot(client, team)


@pytest.mark.django_db
def test_the_welcome_letter_says_how_to_reach_them(django_capture_on_commit_callbacks):
    team, captain = _team()
    Team.objects.filter(pk=team.pk).update(member_contact=GROUP)
    with django_capture_on_commit_callbacks(execute=True):
        mate = _join(team, captain, "mate136c@example.com", "队员136c")
    welcome = next(m for m in mail.outbox if m.to == [mate.email])
    assert GROUP in welcome.body

    Team.objects.filter(pk=team.pk).update(member_contact="")
    with django_capture_on_commit_callbacks(execute=True):
        late = _join(team, captain, "mate136d@example.com", "队员136d")
    welcome = next(m for m in mail.outbox if m.to == [late.email])
    assert "队内联系方式" not in welcome.body


@pytest.mark.django_db
def test_the_service_saves_it_trimmed():
    team, captain = _team()
    fresh = Team.objects.get(pk=team.pk)
    team_services.update_team(
        team=fresh,
        user=captain,
        name=fresh.name,
        description="",
        logo=None,
        is_recruiting=True,
        member_contact=f"  {GROUP}  ",
    )
    assert Team.objects.get(pk=team.pk).member_contact == GROUP


@pytest.mark.django_db
def test_my_teams_lists_how_to_reach_each(client):
    """Round 149 (design 7.1, v6.42)."""
    team, captain = _team()
    mate = _join(team, captain, "mate149@example.com", "队员149")
    client.force_login(mate)
    page = client.get(reverse("me_teams")).content.decode()
    assert "队长还没填" in page
    Team.objects.filter(pk=team.pk).update(member_contact=GROUP)
    page = client.get(reverse("me_teams")).content.decode()
    assert f'<span class="font-code">{GROUP}</span>' in page
    client.force_login(captain)
    Team.objects.filter(pk=team.pk).update(member_contact="")
    assert "还没填，去填" in client.get(reverse("me_teams")).content.decode()
