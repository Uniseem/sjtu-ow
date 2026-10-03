"""Round 140: the team list by the position a team lacks (design 7.6, v6.35)."""

import re

import pytest
from django.urls import reverse

from core.models import SiteSettings
from teams import services as team_services
from teams.models import Team
from tournaments.tests.test_state_table import player


def _team(name, roles="", recruiting=True, members=1):
    captain = player(f"{name}@example.com", name)
    team = team_services.create_team(user=captain, name=name, recruiting_roles=roles)
    for index in range(members - 1):
        mate = player(f"{name}{index}@example.com", f"{name}{index}")
        application = team_services.apply_to_team(
            team=team, user=mate, roles={"tank": True}
        )
        team_services.approve_application(application=application, actor=captain)
    Team.objects.filter(pk=team.pk).update(is_recruiting=recruiting)
    return team


def _names(html):
    return set(re.findall(r"测队[A-Z]", html))


@pytest.fixture
def board(db):
    site = SiteSettings.load()
    site.team_max_members = 2
    site.save()
    _team("测队A", roles="support")
    _team("测队B")
    _team("测队C", roles="tank")
    _team("测队D", roles="support", recruiting=False)
    _team("测队E", roles="support", members=2)


@pytest.mark.django_db
def test_lacking_support_lists_what_a_support_can_join(board, client):
    html = client.get(reverse("team_index"), {"role": "support"}).content.decode()
    assert _names(html) == {"测队A", "测队B"}
    assert re.search(r'aria-current="page" data-role-tab="support"', html)
    tab = re.search(
        r'data-role-tab="support">缺支援<span class="c-tabs__count">(\d+)', html
    )
    assert tab.group(1) == "2"
    tank = re.search(
        r'data-role-tab="tank">缺坦克<span class="c-tabs__count">(\d+)', html
    )
    assert tank.group(1) == "2"  # 测队B wants anyone, 测队C wants a tank


@pytest.mark.django_db
def test_an_unknown_role_shows_everything(board, client):
    html = client.get(reverse("team_index"), {"role": "healer"}).content.decode()
    assert _names(html) == {"测队A", "测队B", "测队C", "测队D", "测队E"}


@pytest.mark.django_db
def test_nobody_lacking_says_so(db, client):
    _team("测队C", roles="tank")
    html = client.get(reverse("team_index"), {"role": "support"}).content.decode()
    assert "暂时没有缺支援的战队" in html
    assert _names(html) == set()
