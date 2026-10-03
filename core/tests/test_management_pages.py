"""Round 116: the member-facing management pages, part two of the review
(handoff/rounds/115-admin-review/findings.md #12–20, #28).

Ranks where captains and members decide, reasons shown before a button is
pressed, ways back from the account pages, the agreement linked at signup,
blocked features said in the standard words, 我的报名 as the design lists
it, the export that keeps its message, a refused comment that keeps its text.
"""

import re
from datetime import timedelta
from io import BytesIO
from unittest import mock

import pytest
from django.contrib.auth.models import Group
from django.core.files.uploadedfile import SimpleUploadedFile
from django.core.management import call_command
from django.urls import reverse
from django.utils import timezone
from PIL import Image as PILImage

from accounts.models import Feature, FeatureUserRule, GameAccount
from tournaments.models import Tournament, TournamentStatus
from tournaments.tests.test_review_admin import _player


@pytest.fixture
def site(db):
    call_command("init_site", verbosity=0)


def _ranked(email, nickname, **ranks):
    user = _player(email, nickname)
    GameAccount.objects.filter(user=user).update(**ranks)
    return user


def _tournament(**extra):
    now = timezone.now()
    values = {
        "title": "管理页测试赛",
        "registration_mode": "team",
        "registration_opens_at": now - timedelta(days=1),
        "registration_closes_at": now + timedelta(days=7),
        "roster_min": 1,
        "roster_max": 3,
        "status": TournamentStatus.PUBLISHED,
        "published_at": now,
    }
    values.update(extra)
    return Tournament.objects.create(**values)


def _register(team, captain, tournament=None):
    from tournaments import registration as reg

    return reg.submit(
        tournament=tournament or _tournament(),
        team=team,
        actor=captain,
        selections={str(captain.pk): captain.game_accounts.first().pk},
    )


# --- the captain's page (#12, #14) ------------------------------------------------


@pytest.mark.django_db
def test_the_captain_sees_ranks_of_members_and_applicants(client, site):
    from teams import services as team_services

    captain = _ranked("cap116@example.com", "队长乙", rank_tank=22)
    applicant = _ranked("app116@example.com", "申请人", rank_support=27)
    team = team_services.create_team(user=captain, name="段位测试队")
    team_services.apply_to_team(team=team, user=applicant, roles={"support": True})
    client.force_login(captain)
    page = client.get(reverse("team_manage", args=[team.pk])).content.decode()
    assert "位置与段位" in page
    roster = page[page.index("位置与段位") :]
    assert "钻石" in roster  # the captain's tank rank, in the member table
    assert "支援 大师 3" in page  # the applicant's game ID with its rank


@pytest.mark.django_db
def test_a_team_that_cannot_disband_says_why_before_the_button(client, site):
    from teams import services as team_services

    captain = _player("blocked116@example.com", "报了名的队长")
    team = team_services.create_team(user=captain, name="报名中的队")
    _register(team, captain)
    client.force_login(captain)
    page = client.get(reverse("team_manage", args=[team.pk])).content.decode()
    assert "管理页测试赛" in page and "暂时不能解散" in page
    assert reverse("team_disband", args=[team.pk]) not in page


@pytest.mark.django_db
def test_the_create_page_says_no_before_the_form(client, site):
    captain = _player("limit116@example.com", "被禁止建队")
    FeatureUserRule.objects.create(
        user=captain, feature=Feature.TEAM_CREATE, allowed=False
    )
    client.force_login(captain)
    page = client.get(reverse("team_create")).content.decode()
    assert "暂时无法使用此功能" in page
    assert 'name="name"' not in page


@pytest.mark.django_db
def test_a_refused_team_leaves_no_logo_and_names_the_field(client, site):
    from wagtail.images.models import Image

    from teams import services as team_services

    team_services.create_team(
        user=_player("first116@example.com", "先来的"), name="同名队"
    )
    late = _player("late116@example.com", "后到的")
    buffer = BytesIO()
    PILImage.new("RGB", (64, 64), (10, 20, 30)).save(buffer, "PNG")
    before = Image.objects.count()
    client.force_login(late)
    with mock.patch("teams.views.over_limit", return_value=False):
        response = client.post(
            reverse("team_create"),
            {
                "name": "同名队",
                "is_recruiting": "on",
                "logo_file": SimpleUploadedFile(
                    "logo.png", buffer.getvalue(), "image/png"
                ),
            },
        )
    assert Image.objects.count() == before  # the logo went with the refusal
    html = response.content.decode()
    assert "已经有同名的战队了" in html and "c-field__error" in html


# --- registrations (#13, #18) -----------------------------------------------------


@pytest.mark.django_db
def test_the_roster_snapshot_and_the_admin_show_ranks(client, site):
    from teams import services as team_services

    captain = _ranked("snap116@example.com", "快照队长", rank_damage=22)
    team = team_services.create_team(user=captain, name="快照队")
    registration = _register(team, captain)
    client.force_login(captain)
    detail = client.get(registration.get_absolute_url()).content.decode()
    assert "段位（提交时）" in detail and "输出 钻石 3" in detail
    manager = _player("mgr116@example.com", "赛事管理")
    manager.groups.add(Group.objects.get(name="赛事管理员"))
    client.force_login(manager)
    admin = client.get(reverse("registration_review_detail", args=[registration.pk]))
    assert "钻石 3" in admin.content.decode()


@pytest.mark.django_db
def test_my_registrations_lists_rosters_i_am_on_and_my_signups_in_full(client, site):
    from teams import services as team_services
    from tournaments import registration as reg
    from tournaments.models import RegistrationMember

    captain = _player("mine116@example.com", "报名的人")
    team = team_services.create_team(user=captain, name="我的报名队")
    current = _register(team, captain, _tournament(title="还在名单上的赛"))
    left = _register(team, captain, _tournament(title="已经不在名单上的赛"))
    RegistrationMember.objects.filter(registration=left).update(is_active=False)
    solo = _tournament(title="已结束的个人赛", registration_mode="individual")
    reg.sign_up_individual(
        tournament=solo,
        user=captain,
        game_account_id=captain.game_accounts.first().pk,
        roles=["tank"],
    )
    Tournament.objects.filter(pk=solo.pk).update(status=TournamentStatus.FINISHED)
    client.force_login(captain)
    page = client.get(reverse("me_registrations")).content.decode()
    assert current.tournament.title in page
    assert "已经不在名单上的赛" not in page
    assert captain.game_accounts.first().battletag in page  # the individual row
    assert "赛事已结束，没有编队" in page and "等待编队" not in page


# --- account pages (#15, #16, #19) ------------------------------------------------


@pytest.mark.django_db
def test_password_and_email_pages_lead_back_to_account_security(client, site):
    member = _player("back116@example.com", "改密码的人")
    client.force_login(member)
    for name in ("account_change_password", "account_email"):
        page = client.get(reverse(name)).content.decode()
        assert reverse("me_security") in page, name
    security = client.get(reverse("me_security")).content.decode()
    assert f'action="{reverse("account_logout")}"' in security


@pytest.mark.django_db
def test_signup_links_the_agreement_and_the_privacy_policy(client, site):
    page = client.get(reverse("account_signup")).content.decode()
    form = page[page.index('action="/accounts/signup/"') :]
    form = form[: form.index("</form>")]  # the footer links them on every page
    assert 'href="/terms/"' in form and 'href="/privacy/"' in form
    assert "内容由社团提供" not in page


@pytest.mark.django_db
def test_the_export_link_is_not_a_download_attribute(client, site):
    member = _player("export116@example.com", "导出的人")
    client.force_login(member)
    page = client.get(reverse("me_security")).content.decode()
    link = re.search(r'<a href="/me/export/"[^>]*>', page).group(0)
    assert "download" not in link and "data-no-loading" in link


# --- blocked features and missing profile items (#17) -----------------------------


@pytest.mark.django_db
def test_an_individual_signup_speaks_to_the_person(site):
    from tournaments import registration as reg

    member = _player("self116@example.com", "自己")
    member.contact_methods.all().delete()
    problems = reg.individual_problems(
        tournament=_tournament(registration_mode="individual"), user=member
    )
    assert "你的资料不完整（缺少联系方式）" in problems
    assert not any("自己" in problem for problem in problems)


@pytest.mark.django_db
def test_signup_notices_link_to_where_the_profile_is_filled_in(client, site):
    member = _player("gaps116@example.com", "缺资料")
    member.contact_methods.all().delete()
    tournament = _tournament(registration_mode="individual")
    client.force_login(member)
    page = client.get(reverse("tournament_individual_signup", args=[tournament.pk]))
    assert reverse("me_contacts") in page.content.decode()


# --- comments (#20) ---------------------------------------------------------------


@pytest.mark.django_db
def test_a_refused_comment_keeps_the_box_and_the_text(client, site):
    from content.models import ArticleCategory, ArticleIndexPage
    from content.tests.test_content import _article

    author = _player("commenter116@example.com", "评论者")
    article = _article(
        ArticleIndexPage.objects.get(slug="news"),
        ArticleCategory.objects.get(slug="guide"),
        author,
        title="评论测试",
        slug="comments-116",
    )
    client.force_login(author)
    with mock.patch("comments.views._too_many", return_value=True):
        response = client.post(
            reverse("comment_create", args=[article.pk]),
            {"body": "我打了好长一段话"},
            HTTP_HX_REQUEST="true",
        )
    html = response.content.decode()
    assert "评论太频繁了" in html
    assert "我打了好长一段话</textarea>" in html


# --- empty states (#28) -----------------------------------------------------------


@pytest.mark.django_db
def test_empty_lists_use_the_empty_state(client, site):
    member = _player("empty116@example.com", "什么都没有")
    client.force_login(member)
    for name, title in (
        ("me_teams", "还没有加入战队"),
        ("me_teams", "还没有提交过入队申请"),
        ("me_registrations", "还没有参加赛事报名"),
        ("me_registrations", "没有个人报名"),
    ):
        page = client.get(reverse(name)).content.decode()
        assert f'<p class="c-empty__title">{title}</p>' in page, title
