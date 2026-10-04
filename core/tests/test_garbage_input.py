"""Rounds 166-167: whatever a visitor, a member or an admin sends, the site
answers with a page, a message, a redirect or a 404, never a 500.

Walks every address the project's own apps define (Wagtail's and allauth's
are theirs), fills in real ids, and sends what a careless or curious person
might: letters where ids go, twenty-digit numbers, empty and huge fields,
dates no calendar has. 165-166 found a public 500 this way
(/comments/99999999999999999999/more/), and three more in forms.
"""

import re
from datetime import timedelta

import pytest
from django.core.management import call_command
from django.test import Client
from django.urls import URLPattern, URLResolver, get_resolver
from django.utils import timezone

PROJECT = (
    "accounts.",
    "comments.",
    "content.",
    "core.",
    "members.",
    "moderation.",
    "scrims.",
    "search.",
    "teams.",
    "tournaments.",
)
HUGE = "99999999999999999999"
POSTS = [
    {},
    {"game_account": "abc", "roles": ["hacker"], "team": "abc", "action": "nope"},
    {"game_account": HUGE, "roles": "tank", "user": "abc", "registration": "abc"},
    {"user": HUGE, "registration": HUGE, "application": HUGE, "action": "approve"},
    {"body": "长" * 5000, "name": "x" * 500, "nickname": "%00", "motto": "x" * 999},
    {"action": "dissolve", "registration": "abc", "user": "-1"},
    {"action": "select", "signups": ["abc", HUGE]},
]
QUERY = {
    "page": "abc",
    "user": "abc",
    "tournament": HUGE,
    "status": "%00",
    "start": "0001-01-01",
    "end": "9999-12-31",
    "category": "%00",
    "q": "%00",
    "role": "x",
    "free": "abc",
    "comments": "abc",
    "sort": "x",
    "slots": "team-join:abc,account",
}
# Last, so the rest still run as a member with a team.
LAST = ("delete", "disband", "leave", "withdraw", "remove")


def _routes():
    found = []

    def walk(patterns, prefix):
        for pattern in patterns:
            if isinstance(pattern, URLResolver):
                walk(pattern.url_patterns, prefix + str(pattern.pattern))
            elif isinstance(pattern, URLPattern):
                module = getattr(pattern.callback, "__module__", "")
                if module.startswith(PROJECT):
                    found.append(prefix + str(pattern.pattern))

    walk(get_resolver().url_patterns, "")
    routes = [route for route in found if "(?P" not in route]
    return sorted(routes, key=lambda route: any(word in route for word in LAST))


@pytest.fixture
def world(db):
    from comments.models import Comment
    from core.tests.test_chapter15_audit import _publish_article, _verified, make_user
    from scrims.models import Scrim, ScrimStatus
    from teams import services as team_services
    from tournaments.tests.test_adhoc_teams import _tournament

    call_command("init_site", verbosity=0)
    member = _verified(make_user(1))
    author = _verified(make_user(2))
    root = _verified(make_user(3))
    root.is_superuser = True
    root.is_staff = True
    root.save()
    article = _publish_article(author)
    ids = {
        "teams": team_services.create_team(user=member, name="随便填队").pk,
        "tournaments": _tournament(title="随便填杯").pk,
        "scrims": Scrim.objects.create(
            title="随便填内战",
            starts_at=timezone.now() + timedelta(days=1),
            status=ScrimStatus.PUBLISHED,
        ).pk,
        "comments": Comment.objects.create(page=article, author=author, body="评").pk,
        "members": member.pk,
        "me/game-accounts": member.game_accounts.first().pk,
    }

    def fill(route):
        route = route.lstrip("^").rstrip("$")
        route = route.replace("<id:page_pk>", str(article.pk))
        # The admin's own pages for these (split, captain, teams) too.
        bare = route.removeprefix("admin/")
        for prefix, value in ids.items():
            if bare.startswith(prefix + "/"):
                route = re.sub(r"<id:\w+>", str(value), route, count=1)
        return "/" + re.sub(r"<[^>]+>", "1", route)

    return {"member": member, "root": root, "fill": fill}


def _crashes(client, method, urls, payloads):
    crashed = []
    for url in urls:
        for payload in payloads:
            response = getattr(client, method)(url, payload)
            # 503 is /healthz saying the worker is down: an answer, not a crash.
            if response.status_code == 500:
                crashed.append((method, url, sorted(payload)))
    return crashed


@pytest.mark.django_db
def test_garbage_posts_never_crash(world):
    urls = [world["fill"](route) for route in _routes()]
    public = [url for url in urls if not url.startswith("/admin/")]
    visitor = Client(raise_request_exception=False)
    member = Client(raise_request_exception=False)
    member.force_login(world["member"])
    root = Client(raise_request_exception=False)
    root.force_login(world["root"])
    crashed = _crashes(visitor, "post", public, POSTS)
    crashed += _crashes(member, "post", urls, POSTS)
    admin = [url for url in urls if url.startswith("/admin/")]
    crashed += _crashes(root, "post", admin, POSTS)
    assert crashed == []


def test_what_counts_as_an_id():
    from core.converters import as_id

    assert as_id("12") == 12 and as_id(" 12 ") == 12 and as_id(7) == 7
    assert as_id("999999999999999999") == 999999999999999999  # 18 digits
    for wrong in (None, "", "abc", "-1", "1.5", "12abc", HUGE):
        assert as_id(wrong) is None, wrong


@pytest.mark.django_db
def test_garbage_queries_never_crash(world):
    urls = [world["fill"](route) for route in _routes()]
    crashed = []
    for who in (None, world["member"], world["root"]):
        client = Client(raise_request_exception=False)
        if who is not None:
            client.force_login(who)
        crashed += _crashes(client, "get", urls, [QUERY])
    assert crashed == []
