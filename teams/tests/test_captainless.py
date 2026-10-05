"""Round 177: a team whose captain is disabled reaches the site owner's to-do
(design 3.7, 14.1, v6.60)."""

import pytest
from django.contrib.messages import get_messages
from django.urls import reverse

from accounts.models import User
from core.admin_todo import todo_rows
from core.tests.test_admin_safety import _player, _superuser, site  # noqa: F401
from teams import services
from teams.models import TeamMembership, TeamRole


def _stop(user):
    User.objects.filter(pk=user.pk).update(is_active=False)


def _row(user):
    return next((row for row in todo_rows(user) if "队长账号已停用" in row.text), None)


@pytest.mark.django_db
def test_which_teams_have_no_working_captain(site):  # noqa: F811
    fine = services.create_team(
        user=_player("ok177@example.com", "好队长"), name="好队"
    )
    gone_captain = _player("gone177@example.com", "停用队长")
    stuck = services.create_team(user=gone_captain, name="卡住的队")
    _stop(gone_captain)
    nobody = services.create_team(user=_player("x177@example.com", "走了"), name="空队")
    TeamMembership.objects.filter(team=nobody, role=TeamRole.CAPTAIN).delete()
    over = services.create_team(
        user=_player("o177@example.com", "解散队长"), name="散了"
    )
    services.disband_team(team=over, actor=over.captain())
    _stop(User.objects.get(email="o177@example.com"))

    assert set(services.teams_without_captain()) == {stuck, nobody}
    assert fine not in services.teams_without_captain()


@pytest.mark.django_db
def test_the_owner_is_told_and_sent_where_to_fix_it(client, site):  # noqa: F811
    admin = _superuser()
    assert _row(admin) is None
    first = _player("a177@example.com", "甲队长")
    team = services.create_team(user=first, name="甲队177")
    _stop(first)
    row = _row(admin)
    assert row.count == 1
    assert row.url == reverse("team_assign_captain", args=[team.pk])

    second = _player("b177@example.com", "乙队长")
    services.create_team(user=second, name="乙队177")
    _stop(second)
    healthy = services.create_team(
        user=_player("c177@example.com", "丙队长"), name="丙队177"
    )
    row = _row(admin)
    assert row.count == 2 and row.url.endswith("?captain=gone")
    client.force_login(admin)
    listing = client.get(row.url).content.decode()
    assert "甲队177" in listing and "乙队177" in listing
    assert healthy.name not in listing
    # Nobody else is told: it is the site owner's job.
    member = _player("e177@example.com", "普通成员177")
    assert _row(member) is None


@pytest.mark.django_db
def test_stopping_a_captain_says_which_teams(client, site):  # noqa: F811
    admin = _superuser()
    captain = _player("cap177@example.com", "要停用的队长")
    services.create_team(user=captain, name="被留下的队")
    client.force_login(admin)
    # v7.6: 停用 is its own button (design 13.17).
    url = reverse("backoffice:user_active", args=[captain.pk])
    response = client.post(url, {"action": "stop", "deactivation_note": "测试停用"})
    captain.refresh_from_db()
    assert not captain.is_active
    said = [str(message) for message in get_messages(response.wsgi_request)]
    assert any("「被留下的队」的队长" in message for message in said), said
