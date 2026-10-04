"""Round 124: a new member's first steps (design 3.1, 5.4.3, v6.20)."""

import re
from datetime import timedelta

import pytest
from allauth.account.models import EmailAddress
from django.contrib.auth.models import Group
from django.core import mail
from django.core.management import call_command
from django.urls import reverse
from django.utils import timezone

from accounts.models import GameAccount, User
from tournaments.models import Tournament, TournamentStatus

PASSWORD = "Correct-Horse-Battery-1"
WELCOME = "欢迎加入社区"


@pytest.fixture
def site(db):
    call_command("init_site", verbosity=0)


def _signup(client, email="newbie124@example.com", next_url=""):
    url = reverse("account_signup") + (f"?next={next_url}" if next_url else "")
    page = client.post(
        url,
        {
            "email": email,
            "nickname": "新人124",
            "password1": PASSWORD,
            "password2": PASSWORD,
            "is_sjtu": "true",
            "agreed_terms": "on",
            "agreed_cross_border": "on",
            "next": next_url,
        },
        follow=True,
    )
    code = re.search(r"\b([A-Z0-9]{6})\b", mail.outbox[-1].body).group(1)
    return page, client.post(page.request["PATH_INFO"], {"code": code}, follow=True)


def _user(email, *groups):
    user = User.objects.create_user(
        email=email,
        password=PASSWORD,
        nickname=email.split("@")[0][:12],
        agreed_terms_at=timezone.now(),
        agreed_cross_border_at=timezone.now(),
    )
    EmailAddress.objects.create(user=user, email=email, verified=True, primary=True)
    for name in groups:
        user.groups.add(Group.objects.get(name=name))
    return user


@pytest.mark.django_db
def test_a_new_member_lands_on_their_profile_with_what_to_do(site, client, settings):
    settings.EMAIL_BACKEND = "django.core.mail.backends.locmem.EmailBackend"
    code_page, landed = _signup(client)
    assert WELCOME not in code_page.content.decode()
    assert landed.request["PATH_INFO"] == reverse("me_profile")
    html = landed.content.decode()
    assert WELCOME in html
    assert "游戏 ID" in html


@pytest.mark.django_db
def test_signing_up_from_a_page_goes_back_there(site, client, settings):
    settings.EMAIL_BACKEND = "django.core.mail.backends.locmem.EmailBackend"
    _code_page, landed = _signup(client, "back124@example.com", next_url="/teams/")
    assert landed.request["PATH_INFO"] == "/teams/"


@pytest.mark.django_db
def test_the_tournament_notice_links_to_what_is_missing(site, client):
    now = timezone.now()
    tournament = Tournament.objects.create(
        title="补全杯",
        registration_mode="individual",
        registration_opens_at=now - timedelta(days=1),
        registration_closes_at=now + timedelta(days=5),
        roster_min=2,
        roster_max=3,
        status=TournamentStatus.PUBLISHED,
        published_at=now,
    )
    client.force_login(_user("gaps124@example.com"))
    html = client.get(tournament.get_absolute_url()).content.decode()
    assert "暂时不能个人报名" in html
    assert f'href="{reverse("me_game_accounts")}"' in html
    assert f'href="{reverse("me_contacts")}"' in html


@pytest.mark.django_db
def test_the_team_notice_links_to_adding_a_game_id(site, client):
    from teams import services as team_services

    captain = _user("cap124@example.com")
    GameAccount.objects.create(user=captain, battletag="Cap#1240")
    team = team_services.create_team(user=captain, name="补全战队")
    client.force_login(_user("noid124@example.com"))
    link = f'href="{reverse("me_game_accounts")}"'
    page = client.get(team.get_absolute_url()).content.decode()
    assert "请先在个人中心添加至少一个游戏 ID" in page
    assert link in page
    fragment = client.get(
        reverse("state_fragment"), {"slots": f"team-join:{team.pk}"}
    ).content.decode()
    assert link in fragment


@pytest.mark.django_db
def test_submitters_get_the_guide_and_editors_do_not(site, client):
    from content.models import ArticleIndexPage

    news = ArticleIndexPage.objects.get(slug="news")
    url = reverse("wagtailadmin_pages:add", args=["content", "articlepage", news.pk])
    client.force_login(_user("writer124@example.com", "投稿者"))
    html = client.get(url).content.decode()
    assert "data-submission-guide" in html
    assert "点底部的「发布」就上线了" in html  # v6.73: no review
    assert "提交给内容审核" not in html
    for number, group in enumerate(("内容编辑", "认证作者")):
        client.force_login(_user(f"staff{number}124@example.com", group, "投稿者"))
        assert "data-submission-guide" not in client.get(url).content.decode()
