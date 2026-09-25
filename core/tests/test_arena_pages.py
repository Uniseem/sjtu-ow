"""Tournament, scrim, team and member pages on the v2.0 design system (round 076).

The page skeletons of design 13.2.8: 赛场列表, 赛场详情 and 名册.
"""

from datetime import timedelta

import pytest
from django.utils import timezone

from members.tests.test_members import person
from scrims import services as scrim_services
from scrims.models import ScrimSignup, ScrimStatus
from scrims.tests.test_scrims import make_scrim
from teams import services as team_services
from tournaments import services as tournament_services
from tournaments.models import Registration, RegistrationStatus, TournamentStatus
from tournaments.tests.test_public_pages import _tournament

DAY = timedelta(days=1)


def _html(client, path):
    response = client.get(path)
    assert response.status_code == 200, path
    return response.content.decode("utf-8")


def _section(html, marker, end="</section>"):
    start = html.index(marker)
    return html[start : html.index(end, start)]


def _approve(tournament, team):
    return Registration.objects.create(
        tournament=tournament,
        team=team,
        team_name=team.name,
        status=RegistrationStatus.APPROVED,
        submitted_by=team.captain(),
    )


# --- tournaments -------------------------------------------------------------------


@pytest.mark.django_db
def test_open_and_upcoming_are_tickets_closed_and_finished_are_rows(client):
    _tournament("报名中的", opens=-DAY, closes=DAY)
    _tournament("快开始的", opens=DAY, closes=2 * DAY)
    _tournament("截止了的", opens=-2 * DAY, closes=-DAY)
    _tournament(
        "结束了的", opens=-3 * DAY, closes=-2 * DAY, status=TournamentStatus.FINISHED
    )
    html = _html(client, "/tournaments/")
    for phase, title in (("open", "报名中的"), ("upcoming", "快开始的")):
        block = _section(html, f'data-phase="{phase}"')
        assert "c-ticket" in block and title in block, phase
    for phase, title in (("closed", "截止了的"), ("finished", "结束了的")):
        block = _section(html, f'data-phase="{phase}"')
        assert "c-ticket" not in block and "<table" in block and title in block


@pytest.mark.django_db
def test_the_list_head_counts_each_phase(client):
    _tournament("甲", opens=-DAY, closes=DAY)
    _tournament("乙", opens=-DAY, closes=2 * DAY)
    _tournament("丙", opens=DAY, closes=2 * DAY)
    head = _section(_html(client, "/tournaments/"), "data-phase-counts", "</header>")
    values = [chunk.split("</span>")[0] for chunk in head.split('c-stat__value">')[1:]]
    assert values == ["2", "1", "0", "0"]


@pytest.mark.django_db
def test_tickets_count_only_approved_teams(client):
    tournament = _tournament("有队伍的", opens=-DAY, closes=DAY)
    captain = person("队长甲")
    kept = team_services.create_team(user=captain, name="通过的队")
    pending = team_services.create_team(user=person("队长乙"), name="待审的队")
    _approve(tournament, kept)
    Registration.objects.create(
        tournament=tournament,
        team=pending,
        team_name=pending.name,
        status=RegistrationStatus.PENDING,
        submitted_by=pending.captain(),
    )
    assert tournament_services.approved_counts([tournament]) == {tournament.pk: 1}
    block = _section(_html(client, "/tournaments/"), 'data-phase="open"')
    assert '<span class="c-meter__count">1</span>' in block


@pytest.mark.django_db
def test_the_detail_head_lists_the_key_facts(client):
    tournament = _tournament("看事实的", opens=-DAY, closes=DAY)
    tournament.allow_individual_signup = True
    tournament.save()
    _approve(tournament, team_services.create_team(user=person("队长"), name="甲队"))
    head = _section(
        _html(client, tournament.get_absolute_url()), "data-key-facts", "</header>"
    )
    for label in ("报名截止", "比赛时间", "每队人数", "已通过", "个人报名"):
        assert label in head, label
    assert '已通过</span><span class="c-stat__value">1<small>队</small>' in head


# --- scrims ---------------------------------------------------------------------


@pytest.mark.django_db
def test_upcoming_scrims_show_signups_against_what_a_match_needs(client):
    scrim = make_scrim(title="要来的", starts_at=timezone.now() + 2 * DAY)
    for index in range(3):
        user = person(f"内战{index}")
        account = user.game_accounts.create(battletag=f"P{index}#1234", rank_tank=20)
        ScrimSignup.objects.create(
            scrim=scrim, user=user, game_account=account, role_tank=True
        )
    finished = make_scrim(
        title="结束的",
        starts_at=timezone.now() - 2 * DAY,
        status=ScrimStatus.FINISHED,
    )
    late = person("后来的")
    ScrimSignup.objects.create(
        scrim=finished,
        user=late,
        game_account=late.game_accounts.create(battletag="Late#1234", rank_tank=20),
        role_tank=True,
    )
    assert scrim_services.signup_totals([scrim]) == {scrim.pk: 3}
    html = _html(client, "/scrims/")
    upcoming = _section(html, 'aria-labelledby="scrims-upcoming"')
    assert "3<span> / 10</span>" in upcoming
    assert upcoming.count('<i class="is-on">') == 3
    assert "结束的" not in upcoming
    finished_block = _section(html, 'aria-labelledby="scrims-finished"')
    assert "结束的" in finished_block and "<table" in finished_block
    assert "1 人" in finished_block


# --- teams --------------------------------------------------------------------------


@pytest.mark.django_db
def test_team_tiles_say_members_against_the_limit(client):
    team_services.create_team(user=person("建队的"), name="五人队")
    team_services.create_team(user=person("不招的"), name="满员队", is_recruiting=False)
    html = _html(client, "/teams/")
    assert f"1 / {team_services.max_members()} 人" in html
    assert team_services.team_totals() == {"team_total": 2, "recruiting_total": 1}


@pytest.mark.django_db
def test_the_team_page_names_its_captain_and_founding_date(client):
    captain = person("创始人")
    team = team_services.create_team(user=captain, name="老队")
    head = _section(_html(client, team.get_absolute_url()), "c-pagehead", "</header>")
    assert "创始人" in head
    assert timezone.localtime(team.created_at).strftime("%Y.%m.%d") in head


# --- members -------------------------------------------------------------------------


@pytest.mark.django_db
def test_the_roster_numbers_people_by_when_they_joined(client):
    person("第三个", joined_days_ago=1)
    person("第一个", joined_days_ago=9)
    person("第二个", joined_days_ago=5)
    roster = _section(_html(client, "/members/"), 'id="all-members"')
    numbers = [
        (
            roster[roster.index(name) - 200 : roster.index(name)]
            .rsplit("data-member-number>", 1)[1]
            .split("<")[0]
        )
        for name in ("第一个", "第二个", "第三个")
    ]
    assert numbers == ["001", "002", "003"]
