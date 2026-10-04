"""Round 115: what the full review of the admin and the management pages found
broken or unsafe (handoff/rounds/115-admin-review/findings.md, part one).

Deleting what can only be cancelled, the open admin account page, Wagtail's
default user screens, the review list without page links, the shown backup
secret, the HTMX edits that lost the list, the delete that crashed, team and
comment screens that could add or hard-delete, and forms that acted without
asking.
"""

import re
from datetime import timedelta
from pathlib import Path
from unittest import mock

import pytest
from allauth.account.models import EmailAddress
from django.conf import settings as django_settings
from django.contrib.auth.models import Group
from django.urls import NoReverseMatch, reverse
from django.utils import timezone

from accounts.models import User
from tournaments.models import Tournament, TournamentStatus
from tournaments.tests.test_review_admin import _player

PASSWORD = "Correct-Horse-Battery-1"


@pytest.fixture
def site(db):
    from django.core.management import call_command

    call_command("init_site", verbosity=0)


@pytest.fixture
def manager(site):
    user = _player("manager115@example.com", "赛事管理")
    user.groups.add(Group.objects.get(name="赛事管理员"))
    return user


@pytest.fixture
def registration(site):
    from teams import services as team_services
    from tournaments import registration as reg

    captain = _player("cap-review115@example.com", "审核队长")
    team = team_services.create_team(user=captain, name="审核战队")
    tournament = _tournament(
        title="审核赛", status=TournamentStatus.PUBLISHED, published_at=timezone.now()
    )
    tournament.roster_min = 1
    tournament.save()
    return reg.submit(
        tournament=tournament,
        team=team,
        actor=captain,
        selections={str(captain.pk): captain.game_accounts.first().pk},
    )


def _superuser():
    return User.objects.create_superuser(
        email="root115@example.com",
        password=PASSWORD,
        nickname="站长",
        agreed_terms_at=timezone.now(),
        agreed_cross_border_at=timezone.now(),
    )


def _tournament(**extra):
    now = timezone.now()
    values = {
        "title": "删除测试赛",
        "registration_mode": "team",
        "registration_opens_at": now - timedelta(days=1),
        "registration_closes_at": now + timedelta(days=7),
        "roster_min": 2,
        "roster_max": 3,
    }
    values.update(extra)
    return Tournament.objects.create(**values)


# --- 1. what can only be cancelled is not deleted ---------------------------------


@pytest.mark.django_db
def test_a_published_tournament_cannot_be_deleted(client, manager):
    published = _tournament(
        status=TournamentStatus.PUBLISHED, published_at=timezone.now()
    )
    client.force_login(manager)
    page = client.get(reverse("tournaments:delete", args=[published.pk]))
    assert page.status_code == 302  # back to editing, with the reason
    client.post(reverse("tournaments:delete", args=[published.pk]))
    assert Tournament.objects.filter(pk=published.pk).exists()
    listing = client.get(reverse("tournaments:index")).content.decode()
    assert reverse("tournaments:delete", args=[published.pk]) not in listing


@pytest.mark.django_db
def test_a_draft_never_published_can_be_deleted(client, manager):
    draft = _tournament()
    client.force_login(manager)
    client.post(reverse("tournaments:delete", args=[draft.pk]))
    assert not Tournament.objects.filter(pk=draft.pk).exists()


@pytest.mark.django_db
def test_a_scrim_with_signups_cannot_be_deleted(client, site):
    from scrims.models import Scrim, ScrimStatus
    from scrims.services import can_delete

    scrim = Scrim.objects.create(
        title="删除测试内战",
        starts_at=timezone.now() + timedelta(days=2),
        status=ScrimStatus.PUBLISHED,
    )
    draft = Scrim.objects.create(
        title="草稿内战", starts_at=timezone.now() + timedelta(days=2)
    )
    assert not can_delete(scrim)
    assert can_delete(draft)
    client.force_login(_superuser())
    client.post(reverse("scrims:delete", args=[scrim.pk]))
    assert Scrim.objects.filter(pk=scrim.pk).exists()
    client.post(reverse("scrims:delete", args=[draft.pk]))
    assert not Scrim.objects.filter(pk=draft.pk).exists()


@pytest.mark.django_db
def test_an_unknown_action_is_not_found(client, manager):
    client.force_login(manager)
    tournament = _tournament()
    response = client.get(reverse("tournament_action", args=[tournament.pk, "explode"]))
    assert response.status_code == 404


# --- 2. the admin account page ----------------------------------------------------


@pytest.mark.django_db
def test_members_cannot_change_their_login_email_in_the_admin(client, site):
    from accounts.services import sync_submitter_group

    member = _player("member115@example.com", "投稿成员")
    EmailAddress.objects.create(
        user=member, email=member.email, verified=True, primary=True
    )
    sync_submitter_group(member)
    assert member.groups.filter(name="投稿者").exists()
    client.force_login(member)
    # v7.0: Wagtail's account page is under /wagtail/, for superusers only.
    response = client.get("/wagtail/account/")
    assert response.status_code == 302 and response["Location"] == "/admin/"
    client.force_login(_superuser())
    page = client.get("/wagtail/account/").content.decode()
    assert 'name="name_email-email"' not in page
    assert 'name="name_email-first_name"' not in page
    assert 'name="avatar-avatar"' not in page
    from wagtail.admin.views.account import email_management_enabled

    assert not email_management_enabled()  # even if the name panel came back


# --- 3. the user screens ----------------------------------------------------------


@pytest.mark.django_db
def test_the_user_page_has_the_sites_fields_not_first_and_last_name(client, site):
    admin = _superuser()
    member = _player("edited115@example.com", "被编辑的人")
    client.force_login(admin)
    page = client.get(
        reverse("backoffice:user_edit", args=[member.pk])
    ).content.decode()
    assert 'name="nickname"' in page and 'name="is_sjtu"' in page
    assert 'name="first_name"' not in page
    assert f"{member.nickname}#1234" in page  # the game ID, read-only
    assert "123456789" in page  # contacts: a superuser may see them


@pytest.mark.django_db
def test_stopping_an_account_needs_a_reason_and_cancels_its_applications(client, site):
    from teams import services as team_services
    from teams.models import ApplicationStatus

    admin = _superuser()
    captain = _player("cap115@example.com", "队长甲")
    member = _player("stopped115@example.com", "要停用的人")
    team = team_services.create_team(user=captain, name="停用测试队")
    application = team_services.apply_to_team(
        team=team, user=member, roles={"tank": True}
    )
    client.force_login(admin)
    url = reverse("backoffice:user_edit", args=[member.pk])
    form = {"nickname": member.nickname, "is_sjtu": "on", "is_active": "on"}
    client.post(url, form)  # still active: saves without a reason
    member.refresh_from_db()
    assert member.is_active
    client.post(url, {**form, "is_active": ""})  # stopping without a reason
    member.refresh_from_db()
    assert member.is_active
    client.post(url, {**form, "is_active": "", "deactivation_note": "冒用他人游戏 ID"})
    member.refresh_from_db()
    application.refresh_from_db()
    assert not member.is_active
    assert member.deactivation_note == "冒用他人游戏 ID"
    assert application.status == ApplicationStatus.CANCELLED


@pytest.mark.django_db
def test_users_are_not_added_or_deleted_in_the_admin(client, site):
    admin = _superuser()
    member = _player("kept115@example.com", "不删的人")
    client.force_login(admin)
    # The back office has no address for either (docs/admin.md 4.4) ...
    for name in ("backoffice:user_new", "backoffice:user_delete"):
        with pytest.raises(NoReverseMatch):
            reverse(name, args=[] if name.endswith("new") else [member.pk])
    listing = client.get(reverse("backoffice:users")).content.decode()
    assert "新建" not in listing and "删除" not in listing
    # ... and Wagtail's own screens under /wagtail/ refuse them.
    assert client.get(reverse("wagtailusers_users:add")).status_code != 200
    client.post(reverse("wagtailusers_users:delete", args=[member.pk]))
    assert User.objects.filter(pk=member.pk).exists()
    listing = client.get(reverse("wagtailusers_users:index")).content.decode()
    assert reverse("wagtailusers_users:add") not in listing


# --- 4. the registration review list ----------------------------------------------


@pytest.mark.django_db
def test_the_review_list_links_to_its_other_pages(client, registration, manager):
    client.force_login(manager)
    second = registration.__class__.objects.get(pk=registration.pk)
    second.pk = None
    second.tournament = _tournament(title="另一项赛事")  # one per team and event
    second.save()
    with mock.patch("tournaments.review_admin.PAGE_SIZE", 1):
        page = client.get(reverse("registration_review_index")).content.decode()
    assert "page=2" in page and "下一页" in page


@pytest.mark.django_db
def test_bulk_approve_stays_on_the_site(client, registration, manager):
    client.force_login(manager)
    response = client.post(
        reverse("registration_review_bulk"),
        {"registration": [registration.pk], "next": "//evil.example.com/"},
    )
    assert response.url == reverse("registration_review_index")


@pytest.mark.django_db
def test_an_adhoc_team_is_not_rejected_from_the_review_page(registration, manager):
    from tournaments import registration as reg

    registration.__class__.objects.filter(pk=registration.pk).update(team=None)
    registration.refresh_from_db()
    with pytest.raises(reg.RegistrationError, match="队伍编排"):
        reg.reject(registration=registration, actor=manager, note="不行")


# --- 5. the backup secret ---------------------------------------------------------


@pytest.mark.django_db
def test_the_backup_secret_is_never_shown_and_blank_keeps_it(client, site):
    from core.models import SiteSettings

    settings_row = SiteSettings.load()
    settings_row.backup_s3_secret_access_key = "very-secret-value"
    settings_row.save()
    client.force_login(_superuser())
    url = f"/admin/settings/core/sitesettings/{settings_row.pk}/"
    page = client.get(url).content.decode()
    assert "very-secret-value" not in page
    from core.forms import SiteSettingsAdminForm

    form_class = type(
        "Form",
        (SiteSettingsAdminForm,),
        {"Meta": type("Meta", (), {"model": SiteSettings, "fields": "__all__"})},
    )
    form = form_class(instance=settings_row)
    from django import forms as django_forms

    widget = form.fields["backup_s3_secret_access_key"].widget
    assert isinstance(widget, django_forms.PasswordInput)
    assert form.initial["backup_s3_secret_access_key"] == ""
    form.cleaned_data = {"backup_s3_secret_access_key": ""}
    assert form.clean_backup_s3_secret_access_key() == "very-secret-value"


# --- 6, 7. the game ID and contact pages ------------------------------------------


@pytest.mark.django_db
def test_a_mistake_in_the_new_contact_form_keeps_the_list(client, site):
    member = _player("contacts115@example.com", "联系方式")
    client.force_login(member)
    page = client.get(reverse("me_contacts") + "?new=1").content.decode()
    form = re.search(r'<form\s[^>]*?hx-post="/me/contacts/"[^>]*>', page, re.S)
    assert 'hx-target="#create-contact"' in form.group(0)  # its own box
    # A second QQ is refused; the answer is just the form for its own box.
    response = client.post(
        reverse("me_contacts"),
        {"type": "qq", "value": "987654321"},
        HTTP_HX_REQUEST="true",
    )
    assert response.status_code == 200
    assert "HX-Retarget" not in response
    assert 'id="contact-list"' not in response.content.decode()
    # A good one replaces the whole list.
    response = client.post(
        reverse("me_contacts"),
        {"type": "wechat", "value": "wx_member115"},
        HTTP_HX_REQUEST="true",
    )
    assert response["HX-Retarget"] == "#contact-list"


@pytest.mark.django_db
def test_cancel_brings_back_the_list_not_the_whole_page(client, site):
    member = _player("cancel115@example.com", "取消的人")
    client.force_login(member)
    for name, list_id in (
        ("me_contacts", "contact-list"),
        ("me_game_accounts", "game-account-list"),
    ):
        response = client.get(reverse(name), HTTP_HX_REQUEST="true").content.decode()
        assert f'id="{list_id}"' in response
        assert "<html" not in response and "c-masthead" not in response


@pytest.mark.django_db
def test_a_game_id_from_a_finished_tournament_can_be_deleted(client, site):
    from tournaments import registration as reg

    member = _player("finished115@example.com", "打完比赛的人")
    tournament = _tournament(
        registration_mode="individual",
        status=TournamentStatus.PUBLISHED,
        published_at=timezone.now(),
    )
    account = member.game_accounts.first()
    signup = reg.sign_up_individual(
        tournament=tournament, user=member, game_account_id=account.pk, roles=["tank"]
    )
    Tournament.objects.filter(pk=tournament.pk).update(status=TournamentStatus.FINISHED)
    client.force_login(member)
    response = client.post(reverse("me_game_account_delete", args=[account.pk]))
    assert response.status_code == 302
    assert not member.game_accounts.exists()
    signup.refresh_from_db()
    assert signup.game_account_id is None


# --- 8, 9. team and comment screens -----------------------------------------------


@pytest.mark.django_db
def test_teams_are_not_added_or_deleted_in_the_admin(client, site):
    from teams import services as team_services
    from teams.models import Team

    captain = _player("teamcap115@example.com", "老队长")
    team = team_services.create_team(user=captain, name="不能删的队")
    client.force_login(_superuser())
    # docs/admin.md 4.4: no 新建, no 删除 — there is no address for either.
    for name in ("teams:add", "teams:delete"):
        with pytest.raises(NoReverseMatch):
            reverse(name, args=[team.pk] if name.endswith("delete") else [])
    listing = client.get(reverse("teams:index")).content.decode()
    assert "新建" not in listing and "删除" not in listing
    assert Team.objects.filter(pk=team.pk).exists()


@pytest.mark.django_db
def test_a_captain_is_not_assigned_to_a_disbanded_or_full_team(site):
    from teams import services as team_services

    admin = _superuser()
    captain = _player("disbanded115@example.com", "散队队长")
    team = team_services.create_team(user=captain, name="已解散的队")
    team_services.disband_team(team=team, actor=admin)
    with pytest.raises(team_services.TeamError, match="解散"):
        team_services.assign_captain(team=team, actor=admin, new_captain=captain)
    full = team_services.create_team(
        user=_player("full115@example.com", "满员队长"), name="满员队"
    )
    outsider = _player("outsider115@example.com", "外人")
    with mock.patch("teams.services.is_full", return_value=True):
        with pytest.raises(team_services.TeamError, match="已满"):
            team_services.assign_captain(team=full, actor=admin, new_captain=outsider)


@pytest.mark.django_db
def test_an_admin_edit_of_a_team_regenerates_its_pages(client, site):
    from teams import services as team_services

    captain = _player("edit115@example.com", "改队名的队长")
    team = team_services.create_team(user=captain, name="原来的名字")
    client.force_login(_superuser())
    with mock.patch("teams.services.on_team_changed") as changed:
        client.post(
            reverse("teams:edit", args=[team.pk]),
            {
                "name": "新名字",
                "description": "",
                "is_recruiting": "on",
                "recruiting_roles": ["tank"],
            },
        )
    team.refresh_from_db()
    assert team.name == "新名字" and team.recruiting_roles == "tank"
    assert changed.call_count == 1


@pytest.mark.django_db
def test_comments_are_hidden_or_pinned_not_added_or_deleted(client, site):
    from comments import services as comment_services
    from comments.models import Comment
    from content.models import ArticleCategory, ArticleIndexPage
    from content.tests.test_content import _article

    author = _player("commenter115@example.com", "评论的人")
    article = _article(
        ArticleIndexPage.objects.get(slug="news"),
        ArticleCategory.objects.get(slug="guide"),
        author,
        title="评论文章",
        slug="comments-115",
    )
    comment = comment_services.create(
        page=article,
        author=author,
        body="开头二十个字只是标题里会出现的部分而已，后面这一句才是只有全文才有的结尾",
    )
    client.force_login(_superuser())
    for name in ("comments:add", "comments:delete", "comments:edit"):
        with pytest.raises(NoReverseMatch):
            reverse(name, args=[comment.pk] if name != "comments:add" else [])
    # Deleting is not one of the list's actions either.
    response = client.post(reverse("comments:action", args=[comment.pk, "delete"]))
    assert response.status_code == 403
    assert Comment.objects.filter(pk=comment.pk).exists()
    listing = client.get(reverse("comments:index")).content.decode()
    assert "只有全文才有的结尾" in listing and "评论的人" in listing  # past the title


# --- 11. asking before acting -----------------------------------------------------

CONFIRMED = [
    ("templates/me/teams.html", "team_leave"),
    ("templates/me/teams.html", "application_cancel"),
    ("templates/me/teams.html", "alumnus_remove"),
    ("templates/me/profile.html", "me_avatar_remove"),
    ("templates/me/registrations.html", "tournament_individual_cancel"),
    ("teams/templates/teams/manage.html", "captain_transfer"),
    ("teams/templates/teams/manage.html", "member_remove"),
    ("teams/templates/teams/manage.html", "team_disband"),
    ("teams/templates/teams/slots/join.html", "team_leave"),
    (
        "tournaments/templates/tournaments/registration_detail.html",
        "registration_withdraw",
    ),
    (
        "tournaments/templates/tournaments/registration_detail.html",
        "registration_leave",
    ),
    (
        "tournaments/templates/tournaments/slots/actions.html",
        "tournament_individual_cancel",
    ),
    ("scrims/templates/scrims/slots/actions.html", "scrim_cancel_signup"),
]


@pytest.mark.parametrize(("path", "url_name"), CONFIRMED)
def test_forms_that_take_something_away_ask_first(path, url_name):
    text = (Path(django_settings.BASE_DIR) / path).read_text(encoding="utf-8")
    forms = [
        line
        for line in text.splitlines()
        if "<form" in line and f"'{url_name}'" in line
    ]
    assert forms and all("data-confirm=" in line for line in forms), path


def test_the_site_script_asks_the_forms_question():
    script = (Path(django_settings.BASE_DIR) / "static" / "js" / "app.js").read_text(
        encoding="utf-8"
    )
    assert (
        'getAttribute("data-confirm")' in script
        and "window.confirm(question)" in script
    )


@pytest.mark.parametrize(
    "path",
    [
        "tournaments/templates/tournaments/admin/teams.html",
        "core/templates/core/prerender/index.html",
        "core/templates/core/fonts/detail.html",
    ],
)
def test_admin_forms_that_take_something_away_ask_first(path):
    """The back office asks through data-confirm (static/js/backoffice.js)."""
    text = (Path(django_settings.BASE_DIR) / path).read_text(encoding="utf-8")
    assert "data-confirm=" in text
    assert "onsubmit=" not in text  # no inline script (docs/admin.md 2)
    script = (
        Path(django_settings.BASE_DIR) / "static" / "js" / "backoffice.js"
    ).read_text(encoding="utf-8")
    assert 'getAttribute("data-confirm")' in script
    assert "window.confirm(message)" in script


@pytest.fixture(autouse=True)
def _groups(db):
    Group.objects.get_or_create(name="投稿者")
