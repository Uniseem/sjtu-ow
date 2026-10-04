"""Round 178: the team page and the captain's page show who has been stopped
(design 3.7; design-details 5.3, 5.5, v6.61)."""

import pytest
from django.core.management import call_command

from accounts.models import User
from teams import services
from teams.models import TeamMembership, TeamRole
from tournaments.tests.test_review_admin import _player


@pytest.fixture
def team(db):
    call_command("init_site", verbosity=0)
    captain = _player("cap179@example.com", "队长179")
    squad = services.create_team(user=captain, name="有人停用的队")
    for email, nickname, motto in (
        ("gone179@example.com", "被停用的人", "停用者的宣言179"),
        ("here179@example.com", "还在的人", "在用者的宣言179"),
    ):
        person = _player(email, nickname)
        User.objects.filter(pk=person.pk).update(motto=motto)
        TeamMembership.objects.create(team=squad, user=person, role=TeamRole.MEMBER)
    User.objects.filter(email="gone179@example.com").update(is_active=False)
    return squad


def test_the_team_page_marks_the_stopped_member(client, team):
    html = client.get(f"/teams/{team.pk}/").content.decode()
    assert html.count("data-account-stopped") == 1
    assert "被停用的人" in html  # still holds a place
    assert "停用者的宣言179" not in html
    assert "在用者的宣言179" in html
    assert "队长179（账号已停用）" not in html


def test_a_stopped_captain_is_said_so_up_top(client, team):
    User.objects.filter(email="cap179@example.com").update(is_active=False)
    html = client.get(f"/teams/{team.pk}/").content.decode()
    assert "队长179（账号已停用）" in html
    assert html.count("data-account-stopped") == 2


def test_nobody_applies_to_a_team_whose_captain_is_stopped(team):
    newcomer = _player("new179@example.com", "想加入的人")
    assert services.can_apply(team, newcomer) == (True, "")
    User.objects.filter(email="cap179@example.com").update(is_active=False)
    assert services.can_apply(team, newcomer) == (False, services.CAPTAIN_STOPPED)


def test_the_captain_sees_whom_to_remove(client, team):
    client.force_login(User.objects.get(email="cap179@example.com"))
    html = client.get(f"/teams/{team.pk}/manage/").content.decode()
    assert html.count("data-account-stopped") == 1
    assert "可以移出、空出名额" in html
