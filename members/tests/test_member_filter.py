"""Round 147: 「全部成员」 for a captain looking for players (design 6.3, v6.40)."""

import re

import pytest

from accounts.models import GameAccount, User
from members.models import MemberGroup, MemberGroupMembership
from members.tests.test_members import person
from teams import services as team_services


def _roster(html):
    start = html.index('id="all-members"')
    block = html[start:]
    return re.findall(r'class="c-roster__name c-stretch" title="([^"]+)"', block)


def _numbers(html):
    start = html.index('id="all-members"')
    return re.findall(r"data-member-number>(\d+)<", html[start:])


@pytest.fixture
def people(db):
    oldest = person("老坦克", joined_days_ago=30)
    support = person("闲着的辅助", joined_days_ago=20)
    busy = person("有队的辅助", joined_days_ago=10)
    person("没填位置", joined_days_ago=5)
    User.objects.filter(pk=oldest.pk).update(main_role="tank")
    User.objects.filter(pk__in=[support.pk, busy.pk]).update(main_role="support")
    GameAccount.objects.create(user=busy, battletag="Busy#1470")
    team_services.create_team(user=busy, name="有人的队")
    group = MemberGroup.objects.create(name="社团干部", is_visible=True)
    MemberGroupMembership.objects.create(group=group, user=oldest, title="社长")


@pytest.mark.django_db
def test_by_usual_position(people, client):
    html = client.get("/members/", {"role": "support"}).content.decode()
    assert _roster(html) == ["闲着的辅助", "有队的辅助"]
    assert _numbers(html) == ["002", "003"]  # their place in the join order
    assert "data-member-group" not in html
    assert '筛出 <span class="font-numeric">2</span> 位' in html


@pytest.mark.django_db
def test_only_people_without_a_team(people, client):
    html = client.get("/members/", {"role": "support", "free": "1"}).content.decode()
    assert _roster(html) == ["闲着的辅助"]
    html = client.get("/members/", {"free": "1"}).content.decode()
    assert "有队的辅助" not in _roster(html)
    assert len(_roster(html)) == 3


@pytest.mark.django_db
def test_no_filter_lists_everyone_and_nobody_matching_says_so(people, client):
    html = client.get("/members/").content.decode()
    assert len(_roster(html)) == 4
    assert "data-member-filter" in html
    assert "data-member-group" in html
    html = client.get("/members/", {"role": "damage"}).content.decode()
    assert "没有符合条件的成员" in html
    html = client.get("/members/", {"role": "healer"}).content.decode()
    assert len(_roster(html)) == 4
