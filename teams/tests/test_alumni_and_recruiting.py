"""现役 and 退役, positions a team is short of, and the team pages that show
them (docs/design-details.md 5; v5.2)."""

import re

import pytest
from django.urls import reverse

from accounts.ranks import encode_rank
from scrims.tests.test_scrims import make_user
from teams import services
from teams.models import LeaveReason, TeamAlumnus, TeamRole
from teams.tests.test_teams import _user

DIAMOND_3 = encode_rank("diamond", 3)


@pytest.fixture
def captain(db):
    return _user("cap@example.com", "队长")


@pytest.fixture
def team(captain):
    return services.create_team(user=captain, name="龙骑", description="老牌战队")


def _join(team, captain, user):
    application = services.apply_to_team(team=team, user=user, roles={"tank": True})
    services.approve_application(application=application, actor=captain)


def _main(response):
    html = response.content.decode("utf-8")
    return html[html.index("<main") : html.index("</main>")]


# --- who becomes 退役 ----------------------------------------------------------


def test_leaving_and_being_removed_are_recorded_as_alumni(team, captain):
    left, removed = _user("l@example.com", "退出的"), _user("r@example.com", "被移的")
    for user in (left, removed):
        _join(team, captain, user)
    joined = team.memberships.get(user=left).joined_at
    services.leave_team(team=team, user=left)
    services.remove_member(team=team, actor=captain, member_user=removed)
    first = TeamAlumnus.objects.get(team=team, user=left)
    assert (first.reason, first.role, first.joined_at) == (
        LeaveReason.LEFT,
        TeamRole.MEMBER,
        joined,
    )
    assert (
        TeamAlumnus.objects.get(team=team, user=removed).reason == LeaveReason.REMOVED
    )
    assert team.memberships.count() == 1  # only the captain is 现役


def test_coming_back_takes_the_person_off_the_alumni(team, captain):
    """One person is not both 现役 and 退役 (5.4)."""
    back = _user("b@example.com", "回来的")
    _join(team, captain, back)
    services.leave_team(team=team, user=back)
    assert TeamAlumnus.objects.filter(team=team, user=back).exists()
    _join(team, captain, back)
    assert not TeamAlumnus.objects.filter(team=team, user=back).exists()


def test_deleting_an_account_takes_its_alumni_records(team, captain):
    gone = _user("g@example.com", "注销的")
    _join(team, captain, gone)
    services.leave_team(team=team, user=gone)
    services.leave_all_teams(gone)
    assert not TeamAlumnus.objects.filter(user=gone).exists()


def test_only_the_person_or_the_captain_can_take_a_record_off(team, captain):
    alum, stranger = _user("a@example.com", "退役的"), _user("s@example.com", "路人")
    _join(team, captain, alum)
    services.leave_team(team=team, user=alum)
    record = TeamAlumnus.objects.get(team=team, user=alum)
    with pytest.raises(services.TeamError):
        services.remove_alumnus(alumnus=record, actor=stranger)
    services.remove_alumnus(alumnus=record, actor=alum)
    assert not TeamAlumnus.objects.filter(pk=record.pk).exists()
    _join(team, captain, alum)
    services.remove_member(team=team, actor=captain, member_user=alum)
    services.remove_alumnus(
        alumnus=TeamAlumnus.objects.get(team=team, user=alum), actor=captain
    )
    assert not TeamAlumnus.objects.filter(team=team).exists()


def test_the_removal_view_goes_back_where_it_came_from(client, team, captain):
    alum = _user("v@example.com", "退役的")
    _join(team, captain, alum)
    services.leave_team(team=team, user=alum)
    record = TeamAlumnus.objects.get(team=team, user=alum)
    client.force_login(alum)
    url = reverse("alumnus_remove", args=[team.pk, record.pk])
    response = client.post(url, {"next": "me"})
    assert response.url == reverse("me_teams")
    assert not TeamAlumnus.objects.filter(pk=record.pk).exists()


# --- the pages -----------------------------------------------------------------


def test_the_team_page_lists_the_roster_and_the_alumni_with_their_months(
    client, team, captain
):
    member = make_user("m@example.com", "现役的", damage=DIAMOND_3)
    member.motto, member.main_role = "开团不怂", "damage"
    member.save()
    _join(team, captain, member)
    alum = _user("x@example.com", "退役的")
    _join(team, captain, alum)
    services.leave_team(team=team, user=alum)
    main = _main(client.get(team.get_absolute_url()))
    roster = main[
        main.index('aria-labelledby="team-roster"') : main.index("team-alumni")
    ]
    assert roster.count("data-roster-member") == 2
    assert "“开团不怂”" in roster and "钻石" in roster
    alumni = main[main.index("data-team-alumni") :]
    record = TeamAlumnus.objects.get(user=alum)
    months = f"{record.joined_at:%Y.%m}"
    assert re.search(rf"退役的</a>.*{re.escape(months)}", alumni, re.S)
    # How someone left is not on the public page (5.3).
    assert "退出" not in alumni and "移除" not in alumni


def test_a_hidden_rank_stays_off_the_team_page(client, team, captain):
    member = make_user("h@example.com", "藏段位", damage=DIAMOND_3)
    member.show_rank = False
    member.save()
    _join(team, captain, member)
    main = _main(client.get(team.get_absolute_url()))
    card = main[main.index("藏段位") :]
    card = card[: card.index("</li>")]
    assert "钻石" not in card


def test_the_captain_sees_how_each_alum_left(client, team, captain):
    alum = _user("y@example.com", "被移的")
    _join(team, captain, alum)
    services.remove_member(team=team, actor=captain, member_user=alum)
    client.force_login(captain)
    html = client.get(reverse("team_manage", args=[team.pk])).content.decode()
    table = html[html.index("data-manage-alumni") :]
    assert "被移的" in table and "被移除" in table and "从名单去掉" in table


def test_my_teams_lists_my_alumni_records(client, team, captain):
    alum = _user("z@example.com", "我退役了")
    _join(team, captain, alum)
    services.leave_team(team=team, user=alum)
    client.force_login(alum)
    html = client.get(reverse("me_teams")).content.decode()
    assert "data-me-alumni" in html and "龙骑" in html[html.index("data-me-alumni") :]


def test_short_positions_show_only_while_recruiting(client, team, captain):
    team.recruiting_roles = "support,tank"
    team.save()
    assert team.wanted_roles == [("tank", "坦克"), ("support", "支援")]
    listing = _main(client.get(reverse("team_index")))
    assert "缺 坦克、支援" in listing
    assert "缺 坦克、支援" in _main(client.get(team.get_absolute_url()))
    team.is_recruiting = False
    team.save()
    assert team.wanted_roles == []
    assert "缺 " not in _main(client.get(reverse("team_index")))


def test_the_team_form_saves_the_short_positions(client, team, captain):
    client.force_login(captain)
    client.post(
        reverse("team_manage", args=[team.pk]),
        {
            "form": "profile",
            "name": "龙骑",
            "description": "",
            "is_recruiting": "on",
            "recruiting_roles": ["support", "damage"],
        },
    )
    team.refresh_from_db()
    assert team.recruiting_roles == "damage,support"


def test_team_cards_lead_with_the_picture(client, team, captain):
    """design-details 1.9, 5.1: the base picture (or logo) first, then words."""
    listing = _main(client.get(reverse("team_index")))
    card = listing[listing.index('<li class="c-teams__item">') :]
    card = card[: card.index("</li>")]
    assert card.index("c-teams__logo c-hue-") < card.index("c-teams__body")
    page = _main(client.get(team.get_absolute_url()))
    head = page[page.index('<header class="c-stage c-stage--team">') :]
    assert re.search(r'<img class="c-stage__img" src="[^"]*/hue-[1-5]\.svg"', head)
