"""Round 185: people who can use the admin find it from the header menu and
the footer (design 13.3, 13.13.3, v6.64); members and visitors do not."""

import re

import pytest
from django.contrib.auth.models import Group
from django.core.management import call_command
from django.urls import reverse

from accounts.models import User
from accounts.tests.test_onboarding import _user

ADMIN = reverse("wagtailadmin_home")


@pytest.fixture
def site(db):
    call_command("init_site", verbosity=0)


def _areas(html):
    menu = re.search(r'<div id="slot-account".*?</details>', html, re.S)
    footer = re.search(r'<nav id="slot-footer-account".*?</nav>', html, re.S)
    return (menu.group(0) if menu else ""), footer.group(0)


def _links(client):
    page = client.get(reverse("members")).content.decode()
    fragment = client.get(
        reverse("state_fragment"), {"slots": "account,footer-account"}
    ).content.decode()
    return [f'href="{ADMIN}"' in area for area in (*_areas(page), *_areas(fragment))]


@pytest.mark.django_db
def test_the_site_owner_is_shown_the_way_in(site, client):
    owner = _user("owner185@example.com")
    User.objects.filter(pk=owner.pk).update(is_superuser=True, is_staff=True)
    client.force_login(owner)
    assert _links(client) == [True, True, True, True]


@pytest.mark.django_db
def test_so_is_a_content_editor(site, client):
    editor = _user("editor185@example.com")
    editor.groups.add(Group.objects.get(name="内容编辑"))
    client.force_login(editor)
    assert _links(client) == [True, True, True, True]


@pytest.mark.django_db
def test_members_and_visitors_are_not(site, client):
    assert not any(_links(client))
    member = _user("member185@example.com")
    # Verified members are submitters and may enter the admin to write;
    # that alone does not put the admin in their menu.
    assert member.groups.filter(name="投稿者").exists()
    assert member.has_perm("wagtailadmin.access_admin")
    client.force_login(member)
    assert _links(client) == [False, False, False, False]
