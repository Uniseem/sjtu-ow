"""Round 199 (docs/admin.md 2, v7.3): each page's permission at the door.

``placed`` lets in only the people the page's tab is for (the same function
that decides whether the tab is drawn), or stricter when the page says so;
the view is not even called for anyone else.
"""

import uuid
from unittest import mock

import pytest
from django.contrib.auth.models import Group, Permission
from django.core.exceptions import PermissionDenied
from django.core.management import call_command
from django.http import HttpResponse
from django.test import RequestFactory
from django.urls import get_resolver, reverse
from django.utils import timezone

from accounts.models import User
from accounts.services import (
    GROUP_CONTENT,
    GROUP_SCRIM,
    GROUP_SUBMITTER,
    GROUP_TOURNAMENT,
)
from accounts.tests.test_onboarding import _user
from backoffice import access
from backoffice.nav import placed, tab_for
from content.models import ArticleCategory
from members.models import MemberGroup

# Pages stricter than their tab (``placed(..., allowed=...)``).
STRICTER = {
    "images/collections/": access.is_superuser,
    "images/collections/<id:pk>/rename/": access.is_superuser,
    "images/collections/<id:pk>/delete/": access.is_superuser,
}
FILLER = {
    "pk": 999999999,
    "action": "nothing",
    "kind": "nothing",
    "batch": uuid.UUID(int=0),  # 「发信」 (design 10.5)
}


@pytest.fixture
def site(db):
    call_command("init_site", verbosity=0)


def _routes():
    admin = next(p for p in get_resolver().url_patterns if str(p.pattern) == "admin/")

    def walk(patterns, prefix=""):
        for pattern in patterns:
            if hasattr(pattern, "url_patterns"):
                yield from walk(pattern.url_patterns, prefix + str(pattern.pattern))
            else:
                yield prefix + str(pattern.pattern), pattern

    for route, pattern in walk(admin.url_patterns):
        if route != "announce/<str:kind>/<id:pk>/":  # places itself by kind
            yield route, pattern


def _with_permission(email, codename, app_label):
    """Inside the back office (access_admin) with one model permission only."""
    # No verified address, so not even 投稿者 (verified members always are).
    user = User.objects.create_user(
        email=email,
        password="Correct-Horse-Battery-1",
        nickname=email.split("@")[0][:12],
        agreed_terms_at=timezone.now(),
        agreed_cross_border_at=timezone.now(),
    )
    user.user_permissions.add(
        Permission.objects.get(
            codename="access_admin", content_type__app_label="wagtailadmin"
        ),
        Permission.objects.get(codename=codename, content_type__app_label=app_label),
    )
    return User.objects.get(pk=user.pk)


def test_the_page_is_refused_before_its_view_runs():
    rf = RequestFactory()
    opened = HttpResponse("opened")
    view = mock.Mock(return_value=opened)
    view.__name__ = "view"
    users_page = placed("members", "users", "users")(view)
    editor = mock.Mock(is_authenticated=True, is_active=True, is_superuser=False)
    editor.has_perm.side_effect = lambda perm: perm == access.ADMIN_PERMISSION
    request = rf.get("/admin/users/")
    request.user = editor
    with pytest.raises(PermissionDenied):
        users_page(request)
    assert view.call_count == 0

    root = mock.Mock(is_authenticated=True, is_active=True, is_superuser=True)
    request.user = root
    assert users_page(request) is opened

    # Stricter than its tab: anyone who may use pictures, but superusers only.
    collections = placed("content", "images", allowed=access.is_superuser)(view)
    with mock.patch.object(access, "uses_images", return_value=True):
        request.user = editor
        with pytest.raises(PermissionDenied):
            collections(request)
    assert view.call_count == 1


def test_a_tab_that_does_not_exist_is_caught_when_the_page_is_placed():
    with pytest.raises(ValueError):
        placed("members", "no-such-tab")


@pytest.mark.django_db
def test_every_back_office_page_keeps_out_whoever_its_tab_is_not_for(site):
    people = [
        _user("member199@example.com", GROUP_SUBMITTER),
        _user("editor199@example.com", GROUP_CONTENT),
        _user("events199@example.com", GROUP_TOURNAMENT),
        _user("scrims199@example.com", GROUP_SCRIM),
    ]
    factory = RequestFactory()
    refused = 0
    for route, pattern in _routes():
        view = pattern.callback
        place = view.backoffice_place
        expected = STRICTER.get(route) or tab_for(place.section, place.tab).allowed
        assert view.backoffice_gate is expected, route
        kwargs = {name: FILLER[name] for name in pattern.pattern.converters}
        for person in people:
            assert access.can_enter(person), person.email
            if expected(person):
                continue
            request = factory.get("/admin/" + route)
            request.user = person
            with pytest.raises(PermissionDenied):
                view(request, **kwargs)
            refused += 1
    assert refused > 150


@pytest.mark.django_db
def test_no_page_tells_an_outsider_whether_an_id_exists(site, client):
    """Category and member-group editing and the split pages used to look the
    object up before the permission: 404 for a wrong id, 403 for a right one."""
    category = ArticleCategory.objects.first()
    group = MemberGroup.objects.create(name="门口测试组")
    client.force_login(_user("outsider199@example.com", GROUP_SUBMITTER))
    for name, real in (
        ("backoffice:category_edit", category.pk),
        ("backoffice:member_group_edit", group.pk),
        ("scrim_split", None),
        ("scrim_split_text", None),
    ):
        for pk in filter(None, (real, 999999999)):
            assert client.get(reverse(name, args=[pk])).status_code == 403, name


@pytest.mark.django_db
def test_the_picture_dialog_is_for_people_who_may_use_pictures(site, client):
    """It used to open for anyone inside, empty for those without pictures."""
    client.force_login(
        _with_permission("noimages199@example.com", "change_tournament", "tournaments")
    )
    assert client.get(reverse("backoffice:image_chooser")).status_code == 403
    client.force_login(_user("member-dialog199@example.com", GROUP_SUBMITTER))
    assert client.get(reverse("backoffice:image_chooser")).status_code == 200


@pytest.mark.django_db
def test_new_and_delete_still_need_their_own_permission(site, client):
    """The tab is 「can change」; adding and deleting categories and member
    groups need more, and stay with the view."""
    category = ArticleCategory.objects.first()
    client.force_login(
        _with_permission("cat199@example.com", "change_articlecategory", "content")
    )
    assert (
        client.get(reverse("backoffice:category_edit", args=[category.pk])).status_code
        == 200
    )
    assert client.get(reverse("backoffice:category_new")).status_code == 403
    response = client.post(reverse("backoffice:category_delete", args=[category.pk]))
    assert response.status_code == 403
    assert ArticleCategory.objects.filter(pk=category.pk).exists()

    group = MemberGroup.objects.create(name="门口分组")
    client.force_login(
        _with_permission("grp199@example.com", "change_membergroup", "members")
    )
    assert (
        client.get(reverse("backoffice:member_group_edit", args=[group.pk])).status_code
        == 200
    )
    assert client.get(reverse("backoffice:member_group_new")).status_code == 403
    assert (
        client.post(
            reverse("backoffice:member_group_delete", args=[group.pk])
        ).status_code
        == 403
    )
    assert MemberGroup.objects.filter(pk=group.pk).exists()

    editor = _user("collections199@example.com", GROUP_CONTENT)
    client.force_login(editor)
    assert access.uses_images(editor)
    assert client.get(reverse("backoffice:collections")).status_code == 403
    assert Group.objects.filter(name=GROUP_CONTENT).exists()


def test_a_section_that_does_not_exist_is_caught_when_the_page_is_placed():
    with pytest.raises(ValueError):
        placed("no-such-section")
