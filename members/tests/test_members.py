"""Member showcase and admin-defined member groups (round 066, design 6)."""

from datetime import timedelta

import pytest
from allauth.account.models import EmailAddress
from django.contrib.auth.models import Group
from django.core.exceptions import ValidationError
from django.core.management import call_command
from django.urls import reverse
from django.utils import timezone

from accounts.models import User
from accounts.services import delete_account, personal_data
from core.models import PrerenderedPage
from members.models import MemberGroup, MemberGroupMembership
from members.services import joined_users
from teams import services as team_services
from teams.models import Team

PASSWORD = "Correct-Horse-Battery-1"


def person(nickname, *, verified=True, active=True, joined_days_ago=0):
    user = User.objects.create_user(
        email=f"{nickname}@example.com",
        password=PASSWORD,
        nickname=nickname,
        is_active=active,
        agreed_terms_at=timezone.now(),
        agreed_cross_border_at=timezone.now(),
    )
    User.objects.filter(pk=user.pk).update(
        date_joined=timezone.now() - timedelta(days=joined_days_ago)
    )
    EmailAddress.objects.create(
        user=user, email=user.email, verified=verified, primary=True
    )
    user.refresh_from_db()
    return user


def _main(client, path="/members/"):
    html = client.get(path).content.decode("utf-8")
    return html[html.index("<main") : html.index("</main>")]


# --- who is shown -------------------------------------------------------------


@pytest.mark.django_db
def test_only_active_users_with_a_verified_email_have_joined():
    shown = person("已加入")
    person("没验证", verified=False)
    person("已停用", active=False)
    assert list(joined_users()) == [shown]


@pytest.mark.django_db
def test_everyone_is_listed_by_join_date_without_private_details(client):
    person("后来的", joined_days_ago=1)
    early = person("先来的", joined_days_ago=9)
    early.game_accounts.create(battletag="Early#1234")
    person("没验证", verified=False)

    html = _main(client)
    everyone = html[html.index('id="all-members"') :]
    assert everyone.index("先来的") < everyone.index("后来的")
    assert "没验证" not in html
    assert '共 <span class="font-numeric">2</span> 位成员' in html
    for private in ("Early#1234", early.email):
        assert private not in html


@pytest.mark.django_db
def test_groups_come_in_order_with_titles_and_teams(client):
    leader = person("甲同学")
    member = person("乙同学")
    team_services.create_team(user=member, name="思源湖电竞")
    second = MemberGroup.objects.create(name="技术组", sort_order=20)
    first = MemberGroup.objects.create(
        name="社团干部", description="负责社团日常", sort_order=10
    )
    MemberGroupMembership.objects.create(
        group=first, user=member, title="", sort_order=2
    )
    MemberGroupMembership.objects.create(
        group=first, user=leader, title="社长", sort_order=1
    )
    MemberGroupMembership.objects.create(group=second, user=member)

    html = _main(client)
    assert html.index("社团干部") < html.index("技术组")
    officers = html[
        html.index(f'id="group-{first.pk}"') : html.index(f'id="group-{second.pk}"')
    ]
    assert officers.index("甲同学") < officers.index("乙同学")
    assert '<span class="c-person__title">社长</span>' in officers
    assert "负责社团日常" in officers
    assert "思源湖电竞" in officers


@pytest.mark.django_db
def test_disbanded_teams_are_not_listed(client):
    captain = person("队长同学")
    team = team_services.create_team(user=captain, name="已解散的队")
    # Disbanding through the service also drops memberships; mark it directly
    # so the page's own filter is what keeps the team off.
    Team.objects.filter(pk=team.pk).update(disbanded_at=timezone.now())
    group = MemberGroup.objects.create(name="干部")
    MemberGroupMembership.objects.create(group=group, user=captain)
    assert "已解散的队" not in _main(client)


@pytest.mark.django_db
def test_hidden_groups_stay_off_the_page_but_their_people_do_not(client):
    someone = person("幕后同学")
    hidden = MemberGroup.objects.create(name="秘密小组", is_visible=False)
    MemberGroupMembership.objects.create(group=hidden, user=someone)
    html = _main(client)
    assert "秘密小组" not in html
    assert "幕后同学" in html


@pytest.mark.django_db
def test_a_group_skips_people_who_have_not_joined(client):
    group = MemberGroup.objects.create(name="干部")
    gone = person("走了的")
    MemberGroupMembership.objects.create(group=group, user=gone)
    User.objects.filter(pk=gone.pk).update(is_active=False)
    html = _main(client)
    assert "走了的" not in html
    assert "这个分组暂时没有成员" in html


# --- admin rules --------------------------------------------------------------


@pytest.mark.django_db
def test_only_joined_users_can_be_added_to_a_group():
    group = MemberGroup.objects.create(name="干部")
    unverified = person("没验证", verified=False)
    with pytest.raises(ValidationError, match="只能选已加入的用户"):
        MemberGroupMembership(group=group, user=unverified).clean()
    MemberGroupMembership(group=group, user=person("可以")).clean()


@pytest.mark.django_db
def test_group_names_are_unique_ignoring_case():
    MemberGroup.objects.create(name="Staff")
    with pytest.raises(ValidationError, match="同名"):
        MemberGroup(name="staff").clean()


@pytest.mark.django_db
def test_the_member_picker_shows_nickname_and_email():
    user = person("重名")
    field = MemberGroupMembership._meta.get_field("user").formfield()
    assert field.label_from_instance(user) == "重名（重名@example.com）"


@pytest.fixture
def admin_url():
    return reverse("backoffice:member_groups")


def _staff(group_name):
    user = person(f"后台{group_name}")
    user.groups.add(Group.objects.get(name=group_name))
    return user


@pytest.mark.django_db
def test_content_editors_manage_member_groups(client, admin_url):
    call_command("init_site", verbosity=0)
    client.force_login(_staff("内容编辑"))
    assert client.get(admin_url).status_code == 200


@pytest.mark.django_db
def test_other_admins_do_not(client, admin_url):
    call_command("init_site", verbosity=0)
    client.force_login(_staff("赛事管理员"))
    assert client.get(admin_url).status_code == 403


# --- regeneration -------------------------------------------------------------


@pytest.fixture
def prerender_on(settings, tmp_path):
    settings.PRERENDER_ENABLED = True
    settings.PRERENDER_ROOT = tmp_path


def _requested():
    return PrerenderedPage.objects.filter(path="/members/").exists()


def _forget():
    PrerenderedPage.objects.all().delete()


@pytest.mark.django_db
def test_group_edits_refresh_the_page(prerender_on):
    user = person("甲")
    _forget()
    group = MemberGroup.objects.create(name="干部")
    assert _requested()
    _forget()
    membership = MemberGroupMembership.objects.create(group=group, user=user)
    assert _requested()
    _forget()
    membership.delete()
    assert _requested()


@pytest.mark.django_db
def test_joining_leaving_and_renaming_refresh_the_page(prerender_on):
    user = person("乙", verified=False)
    _forget()
    EmailAddress.objects.filter(user=user).update(verified=True)
    EmailAddress.objects.get(user=user).save()
    assert _requested()

    _forget()
    user.nickname = "乙改名"
    user.save()
    assert _requested()

    _forget()
    user.is_active = False
    user.save()
    assert _requested()


@pytest.mark.django_db
def test_a_login_does_not_refresh_the_page(prerender_on):
    user = person("丙")
    _forget()
    user.last_login = timezone.now()
    user.save(update_fields=["last_login"])
    assert not _requested()


@pytest.mark.django_db
def test_team_changes_refresh_the_page(prerender_on):
    user = person("丁")
    _forget()
    team_services.create_team(user=user, name="新战队")
    assert _requested()


def test_the_page_is_prerendered(db):
    from core.prerender import page_targets

    assert page_targets()["/members/"] == "members"


# --- accounts -----------------------------------------------------------------


@pytest.mark.django_db
def test_deleting_an_account_removes_its_group_memberships():
    user = person("要注销的")
    group = MemberGroup.objects.create(name="干部")
    MemberGroupMembership.objects.create(group=group, user=user)
    delete_account(user)
    assert not MemberGroupMembership.objects.filter(user=user).exists()


@pytest.mark.django_db
def test_the_export_lists_the_users_groups():
    user = person("导出")
    MemberGroupMembership.objects.create(
        group=MemberGroup.objects.create(name="干部"), user=user, title="社长"
    )
    assert personal_data(user)["member_groups"] == [{"group": "干部", "title": "社长"}]
    assert "lfg_posts" not in personal_data(user)


# --- the LFG board is gone ----------------------------------------------------


@pytest.mark.django_db
def test_the_lfg_board_is_gone(client, settings):
    call_command("init_site", verbosity=0)
    assert "lfg" not in settings.INSTALLED_APPS
    assert client.get("/lfg/").status_code == 404
    home = client.get("/").content.decode("utf-8")
    assert "/lfg/" not in home
    assert 'href="/members/"' in home


# --- the admin, end to end (docs/admin.md 4.4; v7.7 round 203) -----------------


@pytest.fixture
def admin_client(client):
    admin = User.objects.create_superuser(
        email="admin@example.com", password=PASSWORD, nickname="管理员"
    )
    client.force_login(admin)
    return client


JSON = {"HTTP_ACCEPT": "application/json"}


def _group(name="社团干部"):
    return MemberGroup.objects.create(name=name)


@pytest.mark.django_db
def test_an_admin_finds_people_and_adds_them_with_one_click(admin_client):
    group = _group()
    leader, member = person("社长同学"), person("组员同学")
    person("没验证的社长", verified=False)
    found = admin_client.get(
        reverse("backoffice:member_group_people", args=[group.pk]), {"q": "社长"}
    ).json()["results"]
    assert [row["id"] for row in found] == [leader.pk]  # joined people only
    assert found[0]["label"].startswith("社长同学（")
    add = reverse("backoffice:member_group_member_add", args=[group.pk])
    answer = admin_client.post(add, {"user": leader.pk}, **JSON).json()
    assert "社长同学" in answer["replace"]["[data-memberships]"]
    admin_client.post(add, {"user": member.pk}, **JSON)
    rows = list(
        group.memberships.order_by("sort_order").values_list(
            "user__nickname", flat=True
        )
    )
    assert rows == ["社长同学", "组员同学"]  # each one at the end
    # Someone already in is not listed again, nor added twice.
    again = admin_client.get(
        reverse("backoffice:member_group_people", args=[group.pk]), {"q": "同学"}
    ).json()["results"]
    assert again == []
    twice = admin_client.post(add, {"user": member.pk}, **JSON).json()
    assert twice["ok"] is False and "已经在这个分组里了" in twice["problem"]
    assert group.memberships.count() == 2


@pytest.mark.django_db
def test_people_are_reordered_given_posts_and_taken_out(admin_client):
    group = _group()
    first, second = person("甲同学"), person("乙同学")
    add = reverse("backoffice:member_group_member_add", args=[group.pk])
    admin_client.post(add, {"user": first.pk}, **JSON)
    admin_client.post(add, {"user": second.pk}, **JSON)
    lower = group.memberships.get(user=second)
    moved = admin_client.post(
        reverse("backoffice:member_group_member_move", args=[lower.pk]),
        {"direction": "up"},
        **JSON,
    ).json()
    block = moved["replace"]["[data-memberships]"]  # the page gets the new order
    assert block.index("乙同学") < block.index("甲同学")
    order = list(
        group.memberships.order_by("sort_order").values_list("user", flat=True)
    )
    assert order == [second.pk, first.pk]
    title = reverse("backoffice:member_group_member_title", args=[lower.pk])
    saved = admin_client.post(
        title, {"title": "社长、主播"}, HTTP_X_AUTOSAVE="1"
    ).json()
    assert saved["ok"] and group.memberships.get(user=second).title == "社长、主播"
    refused = admin_client.post(
        title, {"title": "一个特别特别长的职务名称"}, HTTP_X_AUTOSAVE="1"
    ).json()
    assert "title" in refused["errors"]
    assert group.memberships.get(user=second).title == "社长、主播"
    admin_client.post(
        reverse("backoffice:member_group_member_remove", args=[lower.pk]), **JSON
    )
    assert list(group.memberships.values_list("user", flat=True)) == [first.pk]


@pytest.mark.django_db
def test_without_the_script_everything_still_works(admin_client):
    """A plain search on the page, plain buttons that come back to it."""
    group = _group()
    someone = person("没脚本的人")
    edit = reverse("backoffice:member_group_edit", args=[group.pk])
    page = admin_client.get(edit, {"q": "没脚本"}).content.decode()
    assert "没脚本的人" in page and "data-person-search" in page
    response = admin_client.post(
        reverse("backoffice:member_group_member_add", args=[group.pk]),
        {"user": someone.pk},
    )
    assert response.status_code == 302 and response.url == edit
    membership = group.memberships.get()
    response = admin_client.post(
        reverse("backoffice:member_group_member_title", args=[membership.pk]),
        {"title": "组长"},
    )
    assert response.status_code == 302
    membership.refresh_from_db()
    assert membership.title == "组长"


@pytest.mark.django_db
def test_someone_who_has_not_joined_cannot_be_added(admin_client):
    group = _group()
    stranger = person("没验证", verified=False)
    answer = admin_client.post(
        reverse("backoffice:member_group_member_add", args=[group.pk]),
        {"user": stranger.pk},
        **JSON,
    ).json()
    assert answer["ok"] is False and "已加入" in answer["problem"]
    assert not group.memberships.exists()


@pytest.mark.django_db
def test_an_unnamed_group_can_be_opened_again(admin_client):
    """「没法再次进入管理」: its link used to be empty (round 203)."""
    group = MemberGroup.objects.create(name="")
    page = admin_client.get(reverse("backoffice:member_groups")).content.decode()
    link = reverse("backoffice:member_group_edit", args=[group.pk])
    assert f'href="{link}">（未命名分组）</a>' in page
    assert "成员展示页上不显示" in page
