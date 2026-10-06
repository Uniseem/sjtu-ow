"""Round 216 (design v7.20): the decisions taken on the 210 review.

A2  only superusers search members by email and see their addresses in the
    back office; everyone else sees 「昵称（#编号）」.
A12 a stopped account shows no picture of its own, only the initial.
B11 the same 「通知全体成员」 goes out at most once in 30 minutes.
13.5 「换一个订阅地址」: the calendar address can be cut off.
"""

from datetime import timedelta

import pytest
from allauth.account.models import EmailAddress
from django.contrib.auth.models import Group
from django.core import signing
from django.core.management import call_command
from django.template.loader import render_to_string
from django.urls import reverse
from django.utils import timezone

from accounts.models import User
from core import calendar_feed
from core import services as core_services
from core.models import Broadcast, SiteSettings
from core.tests.test_chapter15_audit import make_user
from members.models import MemberGroup, MemberGroupMembership
from tournaments import registration as reg
from tournaments.models import Tournament, TournamentStatus
from tournaments.tests.test_state_table import player

PASSWORD = "Correct-Horse-Battery-1"


@pytest.fixture
def site(db):
    call_command("init_site", verbosity=0)


def _person(nickname, email, *groups):
    """A joined member (verified email) whose address does not contain the
    nickname, so a match on one is not a match on the other."""
    user = User.objects.create_user(
        email=email,
        password=PASSWORD,
        nickname=nickname,
        agreed_terms_at=timezone.now(),
        agreed_cross_border_at=timezone.now(),
    )
    EmailAddress.objects.create(user=user, email=email, verified=True, primary=True)
    for name in groups:
        user.groups.add(Group.objects.get(name=name))
    return user


def _editor():
    """内容编辑: may manage member groups and set an article's author, but
    is not a superuser (AGENTS「别只用超级管理员测权限」)."""
    user = _person("编辑216", "editor-a2-216@example.com", "内容编辑")
    assert not user.is_superuser
    return user


def _root():
    return User.objects.create_superuser(
        email="root-a2-216@example.com", password=PASSWORD, nickname="站长216"
    )


# --- A2: emails only for superusers ------------------------------------------


@pytest.mark.django_db
def test_216_a2_a_content_editor_cannot_find_people_by_email(site, client):
    """216, A2: the group's person search matched the email for everyone, so
    a content editor could list addresses by searching 「@」."""
    group = MemberGroup.objects.create(name="干部216")
    hidden = _person("藏邮箱216", "hidden-addr-216@example.com")
    client.force_login(_editor())
    url = reverse("backoffice:member_group_people", args=[group.pk])

    by_email = client.get(url, {"q": "hidden-addr"})
    assert by_email.status_code == 200
    assert by_email.json()["results"] == []
    at_sign = client.get(url, {"q": "@"}).json()["results"]
    assert at_sign == []

    by_name = client.get(url, {"q": "藏邮箱"}).json()["results"]
    assert [row["id"] for row in by_name] == [hidden.pk]
    assert by_name[0]["label"] == f"藏邮箱216（#{hidden.pk}）"
    assert "@" not in by_name[0]["label"]


@pytest.mark.django_db
def test_216_a2_the_group_page_shows_numbers_not_emails_to_a_content_editor(
    site, client
):
    """216, A2: the group page printed each member's email under the name,
    and its plain search (no script) matched emails too."""
    group = MemberGroup.objects.create(name="干部216b")
    member = _person("组员216", "member-addr-216@example.com")
    MemberGroupMembership.objects.create(group=group, user=member)
    _person("藏邮箱216b", "hidden-addr-216b@example.com")
    client.force_login(_editor())
    edit = reverse("backoffice:member_group_edit", args=[group.pk])

    page = client.get(edit)
    assert page.status_code == 200
    html = page.content.decode()
    assert "组员216" in html
    assert "member-addr-216@example.com" not in html
    assert f"#{member.pk}" in html
    assert "搜昵称或邮箱" not in html

    searched = client.get(edit, {"q": "hidden-addr"}).content.decode()
    assert "藏邮箱216b" not in searched
    assert "hidden-addr-216b@example.com" not in searched


@pytest.mark.django_db
def test_216_a2_a_superuser_searches_by_email_and_sees_it(site, client):
    """216, A2: superusers keep searching and seeing addresses."""
    group = MemberGroup.objects.create(name="干部216c")
    hidden = _person("藏邮箱216c", "hidden-addr-216c@example.com")
    member = _person("组员216c", "member-addr-216c@example.com")
    MemberGroupMembership.objects.create(group=group, user=member)
    client.force_login(_root())

    found = client.get(
        reverse("backoffice:member_group_people", args=[group.pk]),
        {"q": "hidden-addr"},
    ).json()["results"]
    assert [row["id"] for row in found] == [hidden.pk]
    assert found[0]["label"] == "藏邮箱216c（hidden-addr-216c@example.com）"

    edit = reverse("backoffice:member_group_edit", args=[group.pk])
    html = client.get(edit).content.decode()
    assert "member-addr-216c@example.com" in html
    searched = client.get(edit, {"q": "hidden-addr"}).content.decode()
    assert "藏邮箱216c" in searched and "hidden-addr-216c@example.com" in searched


@pytest.mark.django_db
def test_216_a2_the_article_author_list_shows_numbers_to_a_content_editor(site, client):
    """216, A2: the 作者 dropdown on an article listed every active member as
    「昵称（邮箱）」 for whoever could set the author."""
    author = _person("作者216", "author-addr-216@example.com")
    client.force_login(_editor())
    page = client.get(reverse("backoffice:article_new"))
    assert page.status_code == 200
    html = page.content.decode()
    assert 'name="author"' in html  # content editors do set the author
    assert f"作者216（#{author.pk}）" in html
    assert "author-addr-216@example.com" not in html


@pytest.mark.django_db
def test_216_a2_the_article_author_list_shows_emails_to_a_superuser(site, client):
    """216, A2: a superuser still tells namesakes apart by address."""
    _person("作者216b", "author-addr-216b@example.com")
    client.force_login(_root())
    html = client.get(reverse("backoffice:article_new")).content.decode()
    assert "作者216b（author-addr-216b@example.com）" in html


# --- A12: a stopped account's own picture -------------------------------------


@pytest.mark.django_db
def test_216_a12_a_stopped_account_shows_the_initial_not_its_picture(
    settings, tmp_path
):
    """216, A12: a deactivated member's uploaded picture kept showing
    wherever their name was; now it is the initial, like a closed account."""
    settings.MEDIA_ROOT = tmp_path
    user = make_user(216)
    assert user.avatar_id is not None
    shown = render_to_string("components/avatar.html", {"person": user, "size": "sm"})
    assert "<img" in shown
    assert user.avatar.get_rendition("fill-88x88").url in shown

    user.is_active = False
    user.save(update_fields=["is_active"])
    stopped = render_to_string("components/avatar.html", {"person": user, "size": "sm"})
    assert "<img" not in stopped
    assert "审" in stopped  # 审计用户216's initial
    big = render_to_string("components/avatar.html", {"person": user, "size": "lg"})
    assert "<img" not in big


# --- B11: 「通知全体成员」 at most once in 30 minutes ---------------------------


@pytest.fixture
def smtp(site):
    row = SiteSettings.load()
    row.smtp_host = "smtp.example.com"
    row.from_address = "noreply@example.com"
    row.save()


def _open_tournament():
    now = timezone.now()
    return Tournament.objects.create(
        title="冷却杯216",
        summary="五人一队。",
        registration_mode="individual",
        registration_opens_at=now - timedelta(days=1),
        registration_closes_at=now + timedelta(days=7),
        roster_min=5,
        roster_max=6,
        status=TournamentStatus.PUBLISHED,
        published_at=now,
    )


@pytest.mark.django_db
def test_216_b11_telling_everyone_again_waits_thirty_minutes(smtp):
    """216, B11: ten clicks on 「通知全体成员」 sent ten mails to the whole
    site. A second one within 30 minutes is refused; after that it goes."""
    assert core_services.EVERYONE_GAP_MINUTES == 30
    manager = _person("赛管216", "manager-b11-216@example.com", "赛事管理员")
    tournament = _open_tournament()
    core_services.announce(kind="tournament", obj=tournament, actor=manager)
    assert Broadcast.objects.count() == 1

    with pytest.raises(core_services.AnnouncementError, match="刚通知过全体成员"):
        core_services.announce(kind="tournament", obj=tournament, actor=manager)
    assert "30 分钟内不再发" in core_services.announcement_problem(
        "tournament", tournament
    )
    assert Broadcast.objects.count() == 1

    # 29 minutes on: still too soon.
    Broadcast.objects.update(created_at=timezone.now() - timedelta(minutes=29))
    with pytest.raises(core_services.AnnouncementError, match="刚通知过全体成员"):
        core_services.announce(kind="tournament", obj=tournament, actor=manager)

    # 31 minutes on: it goes again.
    Broadcast.objects.update(created_at=timezone.now() - timedelta(minutes=31))
    assert core_services.announcement_problem("tournament", tournament) == ""
    again = core_services.announce(kind="tournament", obj=tournament, actor=manager)
    assert again.before == 1 and Broadcast.objects.count() == 2


@pytest.mark.django_db
def test_216_b11_the_gap_is_per_event(smtp):
    """216, B11: telling everyone about one tournament does not hold up
    another."""
    manager = _person("赛管216b", "manager-b11b-216@example.com", "赛事管理员")
    core_services.announce(kind="tournament", obj=_open_tournament(), actor=manager)
    other = _open_tournament()
    assert core_services.announcement_problem("tournament", other) == ""


@pytest.mark.django_db
def test_216_b11_telling_the_people_signed_up_is_not_limited(smtp):
    """216, B11: 「通知报名的人」 goes to a few people and is not held up,
    neither by itself nor by a recent 「通知全体成员」."""
    manager = _person("赛管216c", "manager-b11c-216@example.com", "赛事管理员")
    tournament = _open_tournament()
    entrant = player("entrant-b11-216@example.com", "报名人216")
    reg.sign_up_individual(
        tournament=tournament,
        user=entrant,
        game_account_id=entrant.game_accounts.first().pk,
        roles=["tank"],
    )
    core_services.announce(kind="tournament", obj=tournament, actor=manager)
    for _ in range(2):
        core_services.announce(
            kind="tournament",
            obj=tournament,
            actor=manager,
            audience="participants",
            note="改了时间",
        )
    assert Broadcast.objects.filter(audience="participants").count() == 2


# --- 13.5: 「换一个订阅地址」 ---------------------------------------------------


def _feed(client, raw):
    return client.get(reverse("calendar_feed", args=[raw]))


@pytest.mark.django_db
def test_216_calendar_the_address_people_have_keeps_working(site):
    """216 (calendar): until someone asks for a new address, the token is
    exactly the one handed out since round 195, so phones that subscribed
    keep their calendar."""
    user = _person("日历216", "calendar-216@example.com")
    assert user.calendar_version == 0
    old_format = signing.Signer(salt=calendar_feed.CALENDAR_SALT).sign_object(user.pk)
    assert calendar_feed.token(user) == old_format
    assert calendar_feed.user_for(old_format) == user


@pytest.mark.django_db
def test_216_calendar_a_new_address_cuts_off_the_old_one(site, client):
    """216 (calendar): the address could not be revoked once it leaked.
    「换一个订阅地址」 raises calendar_version; the old address is 404, the
    new one works."""
    user = _person("日历216b", "calendar-216b@example.com")
    old = calendar_feed.token(user)
    assert _feed(client, old).status_code == 200

    client.force_login(user)
    page = client.get(reverse("me_registrations")).content.decode()
    assert reverse("me_calendar_reset") in page and "换一个订阅地址" in page
    assert client.get(reverse("me_calendar_reset")).status_code == 405
    response = client.post(reverse("me_calendar_reset"))
    assert response.status_code == 302
    assert response.url == reverse("me_registrations")

    user.refresh_from_db()
    assert user.calendar_version == 1
    new = calendar_feed.token(user)
    assert new != old
    client.logout()
    assert _feed(client, old).status_code == 404
    assert _feed(client, new).status_code == 200
    assert calendar_feed.user_for(new) == user


@pytest.mark.django_db
def test_216_calendar_an_address_from_an_earlier_change_is_dead_too(site, client):
    """216 (calendar): after two changes, an address signed for version 1
    no longer works; only the current version does."""
    user = _person("日历216c", "calendar-216c@example.com")
    calendar_feed.new_address(user)
    calendar_feed.new_address(user)
    assert user.calendar_version == 2
    signer = signing.Signer(salt=calendar_feed.CALENDAR_SALT)
    assert calendar_feed.user_for(signer.sign_object([user.pk, 1])) is None
    assert calendar_feed.user_for(signer.sign_object(user.pk)) is None
    assert _feed(client, signer.sign_object([user.pk, 1])).status_code == 404
    current = signer.sign_object([user.pk, 2])
    assert calendar_feed.token(user) == current
    assert _feed(client, current).status_code == 200
