import pytest
from django.contrib.auth.models import Group, Permission
from django.core.management import call_command
from django.urls import reverse
from django.utils import timezone

from accounts.models import ContactMethod, ContactType, User
from accounts.services import (
    ALL_PRESET_GROUPS,
    CONTACT_VIEW_GROUPS,
    GROUP_EXTERNAL,
    GROUP_SJTU,
    STAFF_GROUPS,
    add_game_account,
)


def _user(email="me@example.com", **kwargs):
    kwargs.setdefault("nickname", "资料用户")
    kwargs.setdefault("password", "Correct-Horse-Battery-1")
    kwargs.setdefault("agreed_terms_at", timezone.now())
    kwargs.setdefault("agreed_cross_border_at", timezone.now())
    return User.objects.create_user(email=email, **kwargs)


@pytest.mark.django_db
def test_me_pages_require_login(client):
    for name in ("me_profile", "me_game_accounts", "me_contacts", "me_security"):
        response = client.get(reverse(name))
        assert response.status_code == 302
        assert reverse("account_login") in response.url


@pytest.mark.django_db
def test_me_pages_render_for_owner(client):
    user = _user()
    client.force_login(user)
    for name in ("me_profile", "me_game_accounts", "me_contacts", "me_security"):
        response = client.get(reverse(name))
        assert response.status_code == 200
        html = response.content.decode("utf-8")
        assert "资料尚未完整" in html
        assert 'style="' not in html
        assert "我的战队" in html
        assert "我的报名" in html


@pytest.mark.django_db
def test_add_game_account_and_contact_clears_banner(client):
    user = _user()
    client.force_login(user)
    response = client.post(
        reverse("me_game_accounts"),
        {
            "battletag": "Live#1234",
            "rank_tank": "22",
            "rank_damage": "",
            "rank_support": "40",
        },
    )
    assert response.status_code == 302
    assert user.game_accounts.filter(battletag="Live#1234").exists()
    account = user.game_accounts.get()
    assert account.rank_tank == 22
    assert account.rank_support == 40
    response = client.post(
        reverse("me_contacts"),
        {"type": ContactType.QQ, "value": "123456789"},
    )
    assert response.status_code == 302
    html = client.get(reverse("me_profile")).content.decode("utf-8")
    assert "资料尚未完整" not in html


@pytest.mark.django_db
def test_cannot_view_or_edit_another_users_contacts(client):
    owner = _user(email="owner@example.com", nickname="主人")
    stranger = _user(email="stranger@example.com", nickname="路人")
    contact = ContactMethod.objects.create(
        user=owner, type=ContactType.WECHAT, value="wxid_secret"
    )
    add_game_account(owner, battletag="Owner#1000")
    client.force_login(stranger)
    html = client.get(reverse("me_contacts")).content.decode("utf-8")
    assert "wxid_secret" not in html
    response = client.get(reverse("me_contact_edit", args=[contact.pk]))
    assert response.status_code == 404
    response = client.post(reverse("me_contact_delete", args=[contact.pk]))
    assert response.status_code == 404
    assert ContactMethod.objects.filter(pk=contact.pk).exists()


@pytest.mark.django_db
def test_view_contactmethod_permission_assigned_to_event_staff():
    call_command("init_site")
    perm = Permission.objects.get(
        content_type__app_label="accounts",
        codename="view_contactmethod",
    )
    player = _user()
    assert not player.has_perm("accounts.view_contactmethod")
    for name in CONTACT_VIEW_GROUPS:
        group = Group.objects.get(name=name)
        assert perm in group.permissions.all()
    player.groups.add(Group.objects.get(name=CONTACT_VIEW_GROUPS[0]))
    player = User.objects.get(pk=player.pk)
    assert player.has_perm("accounts.view_contactmethod")


@pytest.mark.django_db
def test_init_site_is_idempotent_and_keeps_memberships():
    user = _user(is_sjtu=True)
    call_command("init_site")
    extra = Group.objects.create(name="违规观察名单")
    user.groups.add(extra)
    first_names = set(
        Group.objects.filter(name__in=ALL_PRESET_GROUPS).values_list("name", flat=True)
    )
    assert first_names == set(ALL_PRESET_GROUPS)
    call_command("init_site")
    assert Group.objects.filter(name__in=ALL_PRESET_GROUPS).count() == len(
        ALL_PRESET_GROUPS
    )
    names = set(user.groups.values_list("name", flat=True))
    assert extra.name in names
    assert GROUP_SJTU in names
    assert GROUP_EXTERNAL not in names
    for name in STAFF_GROUPS:
        group = Group.objects.get(name=name)
        assert group.permissions.filter(
            content_type__app_label="wagtailadmin",
            codename="access_admin",
        ).exists()
