"""Signing in has one door, allauth's (218, 217 review 04-1).

Wagtail brings two login pages of its own. Both call Django's ``authenticate()``
directly, so they skipped allauth's failed-login limit and its verified-email
rule: an account that never confirmed its email signed in through them, and
anyone's password, the superuser's included, could be guessed without limit.
"""

import pytest
from django.core.management import call_command
from django.urls import get_resolver, resolve

from accounts.views import login_door
from members.tests.test_members import person

SIDE_DOORS = ["/wagtail/login/", "/_util/login/"]


def _signed_in(client):
    return client.session.get("_auth_user_id") is not None


def _routes(patterns=None, prefix=""):
    for entry in patterns or get_resolver().url_patterns:
        route = prefix + str(entry.pattern)
        if hasattr(entry, "url_patterns"):
            yield from _routes(entry.url_patterns, route)
        else:
            yield route, entry


@pytest.mark.django_db
@pytest.mark.parametrize("path", SIDE_DOORS)
def test_a_side_door_only_points_to_the_front_door(client, path):
    response = client.get(path)
    assert response.status_code == 302
    assert response["Location"] == "/accounts/login/"


@pytest.mark.django_db
@pytest.mark.parametrize("path", SIDE_DOORS)
def test_the_way_back_survives_only_when_it_stays_on_the_site(client, path):
    assert (
        client.get(path, {"next": "/me/"})["Location"]
        == "/accounts/login/?next=%2Fme%2F"
    )
    for outside in (
        "https://evil.example/x",
        "//evil.example/x",
        "javascript:alert(1)",
    ):
        assert client.get(path, {"next": outside})["Location"] == "/accounts/login/"


@pytest.mark.django_db
@pytest.mark.parametrize("path", SIDE_DOORS)
@pytest.mark.parametrize("verified", [False, True])
def test_a_side_door_never_signs_anyone_in(client, path, verified):
    """Not the unverified account that the old page let through, and not the
    verified one either: the door is not a door."""
    user = person("侧门", verified=verified)
    for _ in range(8):  # also what a password guesser would do
        response = client.post(path, {"username": user.email, "password": "wrong"})
        assert response.status_code == 302
    response = client.post(
        path, {"username": user.email, "password": "Correct-Horse-Battery-1"}
    )
    assert response.status_code == 302
    assert response["Location"] == "/accounts/login/"
    assert not _signed_in(client)


@pytest.mark.django_db
def test_the_front_door_still_asks_for_a_verified_email(client):
    user = person("正门", verified=False)
    client.post(
        "/accounts/login/",
        {"login": user.email, "password": "Correct-Horse-Battery-1"},
    )
    assert not _signed_in(client)


@pytest.mark.django_db
def test_a_restricted_page_sends_visitors_to_the_front_door(client):
    from wagtail.models import PageViewRestriction

    from content.models import ArticleCategory, ArticleIndexPage
    from content.tests.test_content import _article

    call_command("init_site", verbosity=0)
    article = _article(
        ArticleIndexPage.objects.get(slug="news"),
        ArticleCategory.objects.get(slug="guide"),
        person("作者"),
        title="私密",
        slug="private-one",
    )
    PageViewRestriction.objects.create(
        page=article, restriction_type=PageViewRestriction.LOGIN
    )
    response = client.get("/news/private-one/")
    assert response.status_code == 302
    assert response["Location"].startswith("/accounts/login/?next=")


@pytest.mark.django_db
def test_the_wagtail_admin_sends_visitors_to_the_front_door(client):
    response = client.get("/wagtail/")
    assert response.status_code == 302
    assert response["Location"].startswith("/accounts/login/")


def test_every_login_address_is_served_by_allauth_or_the_side_door_redirect():
    """A Wagtail or Django upgrade that mounts another login view fails here.
    What counts is who answers the address, not what is registered: Wagtail's
    own two patterns are still in the list, behind ours."""
    seen = []
    for route, entry in _routes():
        if "login" not in route and "login" not in (entry.name or ""):
            continue
        assert "<" not in route, f"{route}: check this one by hand"
        seen.append(route)
        match = resolve("/" + route)
        callback = getattr(match.func, "view_class", match.func)
        owner = getattr(callback, "__module__", "")
        name = getattr(callback, "__name__", callback)
        assert owner.startswith("allauth.") or match.func is login_door, (
            f"/{route} is answered by {owner}.{name}"
        )
    assert "accounts/login/" in seen
    assert "wagtail/login/" in seen and "_util/login/" in seen
