"""A person's picture (design-details 2.3, v6.1, round 101).

Nothing sets it yet (no upload, not in the admin). Wherever a face is drawn
it shows the picture when there is one and the 底图 with the initial
otherwise; the pages printing it are regenerated when it changes, an account
deletion drops it, and a list of faces costs the same whatever its length.
"""

from datetime import timedelta
from pathlib import Path
from unittest import mock

import pytest
from django.conf import settings as django_settings
from django.core.management import call_command
from django.template.loader import render_to_string
from django.utils import timezone

from core.tests.test_chapter15_audit import (
    assert_no_n_plus_one,
    make_avatar,
    make_user,
)

PASSWORD = "Correct-Horse-Battery-1"


@pytest.fixture(autouse=True)
def _media(settings, tmp_path):
    settings.MEDIA_ROOT = tmp_path


def _verified(user):
    from allauth.account.models import EmailAddress

    EmailAddress.objects.create(
        user=user, email=user.email, verified=True, primary=True
    )
    return user


def _thumb(user, spec):
    """The address of this person's picture cut to `spec`."""
    return user.avatar.get_rendition(spec).url


# --- the component -------------------------------------------------------------


@pytest.mark.django_db
def test_a_face_is_the_picture_when_there_is_one():
    user = make_user(1)
    html = render_to_string("components/avatar.html", {"person": user, "size": "md"})
    assert _thumb(user, "fill-176x176") in html
    assert "审" not in html  # no initial over the picture
    small = render_to_string("components/avatar.html", {"person": user, "size": "sm"})
    assert _thumb(user, "fill-88x88") in small


@pytest.mark.django_db
def test_without_a_picture_a_face_is_the_initial_on_its_scene():
    user = make_user(2)
    user.avatar = None
    user.save()
    html = render_to_string("components/avatar.html", {"person": user})
    assert "<img" not in html
    assert "审" in html
    assert "c-hue-" in html
    plain = render_to_string("components/avatar.html", {"person": user, "plain": True})
    assert "c-hue-" not in plain
    assert 'aria-hidden="true"' in plain  # the name is always printed beside it


def test_no_template_draws_a_face_by_hand():
    """Every initial-on-a-square goes through the component, so a picture
    shows up everywhere at once (the member card checks for one itself)."""
    offenders = []
    for root in (Path(django_settings.BASE_DIR),):
        for path in root.rglob("*.html"):
            if any(
                part in {".venv", "node_modules", "prerendered"} for part in path.parts
            ):
                continue
            if path.name == "avatar.html":
                continue
            for number, line in enumerate(
                path.read_text(encoding="utf-8").splitlines(), 1
            ):
                if "nickname|initial" in line and "avatar_id" not in line:
                    offenders.append(f"{path.as_posix()}:{number}")
    assert offenders == []


# --- where faces are -----------------------------------------------------------


@pytest.fixture
def site(db):
    call_command("init_site", verbosity=0)


@pytest.mark.django_db
def test_the_member_page_shows_the_picture_on_the_card_and_in_the_list(client, site):
    from members.models import MemberGroup, MemberGroupMembership

    user = _verified(make_user(3))
    group = MemberGroup.objects.create(name="管理组")
    MemberGroupMembership.objects.create(group=group, user=user, title="社长")
    html = client.get("/members/").content.decode()
    assert _thumb(user, "fill-400x400") in html  # the big card (4.2)
    assert _thumb(user, "fill-176x176") in html  # 全部成员 (4.4)
    detail = client.get(f"/members/{user.pk}/").content.decode()
    assert _thumb(user, "fill-176x176") in detail


@pytest.mark.django_db
def test_the_team_page_shows_members_and_former_members(client, site):
    from teams import services as team_services
    from teams.models import LeaveReason, TeamAlumnus, TeamRole

    captain = make_user(4)
    former = make_user(5)
    team = team_services.create_team(user=captain, name="头像战队")
    now = timezone.now()
    TeamAlumnus.objects.create(
        team=team,
        user=former,
        role=TeamRole.MEMBER,
        joined_at=now - timedelta(days=90),
        left_at=now - timedelta(days=3),
        reason=LeaveReason.LEFT,
    )
    html = client.get(team.get_absolute_url()).content.decode()
    assert _thumb(captain, "fill-176x176") in html
    assert _thumb(former, "fill-88x88") in html


@pytest.mark.django_db
def test_an_article_shows_the_author_and_the_commenters(client, site):
    from comments import services as comment_services
    from content.models import ArticleCategory, ArticleIndexPage
    from content.tests.test_content import _article

    author = make_user(6)
    reader = make_user(7)
    news = ArticleIndexPage.objects.get(slug="news")
    article = _article(
        news,
        ArticleCategory.objects.get(slug="guide"),
        author,
        title="头像文章",
        slug="avatar-article",
    )
    comment_services.create(page=article, author=reader, body="写得好")
    html = client.get(article.url).content.decode()
    assert _thumb(author, "fill-88x88") in html  # the byline
    assert _thumb(author, "fill-176x176") in html  # the author card
    assert _thumb(reader, "fill-88x88") in html
    home = client.get("/").content.decode()
    assert _thumb(author, "fill-88x88") in home  # the card's byline


@pytest.mark.django_db
def test_the_individual_pool_shows_faces(client, site):
    from tournaments.models import IndividualSignup

    tournament = _individual_tournament()
    user = make_user(8)
    IndividualSignup.objects.create(
        tournament=tournament,
        user=user,
        game_account=user.game_accounts.first(),
        role_damage=True,
    )
    html = client.get(f"/tournaments/{tournament.pk}/").content.decode()
    assert _thumb(user, "fill-176x176") in html


@pytest.mark.django_db
def test_the_account_menu_shows_your_own_picture(client, site):
    user = _verified(make_user(9))
    client.force_login(user)
    html = client.get("/teams/").content.decode()
    assert _thumb(user, "fill-88x88") in html


# --- keeping pages and data right ----------------------------------------------


@pytest.mark.django_db
def test_a_new_picture_regenerates_the_pages_that_show_it():
    user = make_user(10)
    with mock.patch("accounts.signals.refresh_nickname_pages") as refresh:
        user.avatar = make_avatar(110)
        user.save()
        assert refresh.call_count == 1
        user.avatar = None
        user.save(update_fields=["avatar"])
        assert refresh.call_count == 2
        user.save(update_fields=["last_login"])
        assert refresh.call_count == 2


@pytest.mark.django_db
def test_a_former_members_team_page_is_regenerated_too():
    """Former members are listed with their face (design-details 5.3)."""
    from accounts.services import refresh_nickname_pages
    from teams import services as team_services
    from teams.models import LeaveReason, TeamAlumnus, TeamRole

    team = team_services.create_team(user=make_user(11), name="旧东家")
    former = make_user(12)
    now = timezone.now()
    TeamAlumnus.objects.create(
        team=team,
        user=former,
        role=TeamRole.MEMBER,
        joined_at=now - timedelta(days=90),
        left_at=now,
        reason=LeaveReason.LEFT,
    )
    with mock.patch("core.prerender.request_page") as request_page:
        refresh_nickname_pages(former)
    assert team.get_absolute_url() in [c.args[0] for c in request_page.call_args_list]


@pytest.mark.django_db
def test_deleting_the_account_drops_the_picture():
    from accounts.services import delete_account

    user = make_user(13)
    delete_account(user)
    user.refresh_from_db()
    assert user.avatar_id is None


# --- lists of faces (design 15.1) ----------------------------------------------


def _individual_tournament():
    from tournaments.models import RegistrationMode, Tournament, TournamentStatus

    now = timezone.now()
    return Tournament.objects.create(
        title="个人报名赛",
        registration_mode=RegistrationMode.INDIVIDUAL,
        registration_opens_at=now - timedelta(days=1),
        registration_closes_at=now + timedelta(days=7),
        status=TournamentStatus.PUBLISHED,
        published_at=now,
    )


@pytest.mark.django_db
def test_no_n_plus_one_on_a_team_page(client, site, settings):
    from core.models import SiteSettings
    from teams import services as team_services
    from teams.models import LeaveReason, TeamAlumnus, TeamMembership, TeamRole

    SiteSettings.objects.update(team_max_members=20)
    team = team_services.create_team(user=make_user(200), name="满员战队")
    from accounts.models import User

    def seed(count):
        start = User.objects.count() + 200
        now = timezone.now()
        for index in range(count):
            TeamMembership.objects.create(team=team, user=make_user(start + index))
            TeamAlumnus.objects.create(
                team=team,
                user=make_user(start + index + 100),
                role=TeamRole.MEMBER,
                joined_at=now - timedelta(days=90),
                left_at=now,
                reason=LeaveReason.LEFT,
            )

    assert_no_n_plus_one(client, team.get_absolute_url(), seed)


@pytest.mark.django_db
def test_no_n_plus_one_on_the_individual_pool(client, site):
    from accounts.models import User
    from tournaments.models import IndividualSignup

    tournament = _individual_tournament()

    def seed(count):
        start = User.objects.count() + 400
        for index in range(count):
            user = make_user(start + index)
            IndividualSignup.objects.create(
                tournament=tournament,
                user=user,
                game_account=user.game_accounts.first(),
                role_support=True,
            )

    assert_no_n_plus_one(client, f"/tournaments/{tournament.pk}/", seed)


@pytest.mark.django_db
def test_no_n_plus_one_on_an_article_with_comments(client, site):
    from accounts.models import User
    from comments import services as comment_services
    from content.models import ArticleCategory, ArticleIndexPage
    from content.tests.test_content import _article

    news = ArticleIndexPage.objects.get(slug="news")
    article = _article(
        news,
        ArticleCategory.objects.get(slug="guide"),
        make_user(600),
        title="热闹的文章",
        slug="busy-article",
    )

    def seed(count):
        start = User.objects.count() + 600
        for index in range(count):
            comment = comment_services.create(
                page=article, author=make_user(start + index), body="顶"
            )
            comment_services.create(
                page=article,
                author=make_user(start + index + 100),
                body="同意",
                parent=comment,
            )

    assert_no_n_plus_one(client, article.url, seed)


@pytest.mark.django_db
def test_no_n_plus_one_on_the_article_list(client, site):
    from accounts.models import User
    from content.models import ArticleCategory, ArticleIndexPage
    from content.tests.test_content import _article

    news = ArticleIndexPage.objects.get(slug="news")
    category = ArticleCategory.objects.get(slug="guide")

    def seed(count):
        start = User.objects.count() + 800
        for index in range(count):
            _article(
                news,
                category,
                make_user(start + index),
                title=f"第 {start + index} 篇",
                slug=f"many-{start + index}",
            )

    assert_no_n_plus_one(client, news.url, seed)
