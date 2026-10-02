"""The member page's cards (docs/design-details.md 1.3, 1.4, 1.9, 4; v5.2):
picture first, posts, motto, positions and rank, teams."""

import re

import pytest
from django.core.exceptions import ValidationError

from accounts.models import GameAccount
from accounts.ranks import encode_rank
from members.models import MemberGroup, MemberGroupMembership
from members.services import split_titles
from members.tests.test_members import _main, person
from teams import services as team_services

DIAMOND_3 = encode_rank("diamond", 3)


def _card(html, nickname):
    start = html.rindex('<li class="c-person">', 0, html.index(f">{nickname}<"))
    return html[start : html.index("</li>", start)]


def test_one_field_can_hold_several_posts():
    assert split_titles("社长、主播") == ["社长", "主播"]
    assert split_titles(" 社长 / 主播，解说 ") == ["社长", "主播", "解说"]
    assert split_titles("") == []


@pytest.mark.django_db
def test_each_post_is_ten_characters_at_most():
    group = MemberGroup.objects.create(name="干部")
    user = person("长职务")
    entry = MemberGroupMembership(group=group, user=user, title="社长、" + "很" * 11)
    with pytest.raises(ValidationError):
        entry.full_clean()
    MemberGroupMembership(group=group, user=user, title="社长、主播").full_clean()


@pytest.mark.django_db
def test_a_card_shows_its_groups_posts_motto_play_and_teams(client):
    group = MemberGroup.objects.create(name="干部")
    user = person("全都有")
    user.motto, user.main_role = "推车不停", "damage"
    user.save()
    GameAccount.objects.create(
        user=user, battletag="全都有#1234", rank_damage=DIAMOND_3
    )
    MemberGroupMembership.objects.create(group=group, user=user, title="社长、主播")
    card = _card(_main(client), "全都有")
    # Picture first (1.9, 4.2).
    assert re.match(
        r'<li class="c-person">\s*<span class="c-person__pic c-hue-[1-5]"', card
    )
    assert card.count('<span class="c-person__title">') == 2
    assert "“推车不停”" in card
    assert 'class="c-role c-role--main"' in card and "钻石" in card


@pytest.mark.django_db
def test_more_than_three_posts_and_two_teams_are_counted_not_listed(client):
    """1.4: three posts then 「+N」; two teams then 「等 N 支战队」."""
    group = MemberGroup.objects.create(name="组")
    user = person("身兼数职")
    GameAccount.objects.create(user=user, battletag="身兼数职#1234")  # to apply
    MemberGroupMembership.objects.create(
        group=group, user=user, title="社长、主播、解说、裁判"
    )
    for name in ("一队", "二队", "三队"):
        captain = person(f"{name}长")
        team = team_services.create_team(user=captain, name=name)
        application = team_services.apply_to_team(
            team=team, user=user, roles={"tank": True}
        )
        team_services.approve_application(application=application, actor=captain)
    card = _card(_main(client), "身兼数职")
    assert card.count('<span class="c-person__title">') == 3
    assert '<span class="c-person__more">+1</span>' in card
    assert re.search(r"等 <span[^>]*>3</span> 支战队", card)


@pytest.mark.django_db
def test_the_roster_card_shows_posts_across_groups(client):
    first = MemberGroup.objects.create(name="干部", sort_order=1)
    second = MemberGroup.objects.create(name="赛事组", sort_order=2)
    user = person("两个组")
    MemberGroupMembership.objects.create(group=first, user=user, title="社长")
    MemberGroupMembership.objects.create(group=second, user=user, title="")
    plain = person("只在组里")
    MemberGroupMembership.objects.create(group=second, user=plain, title="")
    html = _main(client)
    roster = html[html.index('<ol class="c-roster"') :]

    def tags(nickname):
        card = roster[roster.index(f">{nickname}<") :]
        return re.findall(
            r'<span class="c-tag">([^<]+)</span>', card[: card.index("</li>")]
        )

    assert tags("两个组") == ["社长"]  # posts win over group names
    assert tags("只在组里") == ["赛事组"]


@pytest.mark.django_db
def test_a_member_without_extras_has_no_empty_lines(client):
    """1.2: what is missing is left out, not written as 「暂无」."""
    group = MemberGroup.objects.create(name="组")
    user = person("什么都没有")
    MemberGroupMembership.objects.create(group=group, user=user)
    card = _card(_main(client), "什么都没有")
    for part in ("c-person__titles", "c-person__motto", "c-play", "c-person__meta"):
        assert part not in card, part
    assert "暂无" not in card and "未填写" not in card
