"""Round 157: 「订阅到手机日历」 (design 13.5, v6.49)."""

from datetime import timedelta

import pytest
from django.core.management import call_command
from django.urls import reverse
from django.utils import timezone

from core import calendar_feed
from scrims.tests.test_my_placement import _place, _scrim, _signup


@pytest.fixture
def site(db):
    call_command("init_site", verbosity=0)


def _feed(client, user):
    return client.get(reverse("calendar_feed", args=[calendar_feed.token(user)]))


@pytest.mark.django_db
def test_my_scrims_become_calendar_events(site, client):
    scrim = _scrim()
    scrim.title = (
        "国庆特别场 · 6v6 怀旧 · 欢迎新人一起来打，打完一起吃夜宵"  # long: folded
    )
    scrim.save(update_fields=["title"])
    me, mine = _signup(scrim, "cal157@example.com", "日历157")
    _place(mine, "b", "tank")
    from tournaments import registration as reg
    from tournaments.tests.test_adhoc_teams import _tournament

    reg.sign_up_individual(
        tournament=_tournament(title="没时间杯157"),
        user=me,
        game_account_id=me.game_accounts.first().pk,
        roles=["tank"],
    )
    response = _feed(client, me)
    assert response.status_code == 200
    assert response["Content-Type"].startswith("text/calendar")
    raw = response.content.decode()
    assert raw.startswith("BEGIN:VCALENDAR\r\n") and raw.endswith("END:VCALENDAR\r\n")
    assert all(len(line.encode()) <= 75 for line in raw.split("\r\n"))
    body = raw.replace("\r\n ", "")  # unfold (RFC 5545 3.1)
    start = timezone.localtime(scrim.starts_at, timezone.UTC)
    assert f"DTSTART:{start:%Y%m%dT%H%M%SZ}" in body
    end = start + timedelta(hours=3)
    assert f"DTEND:{end:%Y%m%dT%H%M%SZ}" in body
    assert f"SUMMARY:内战：{scrim.title}" in body
    assert "B 队 · 坦克" in body
    assert body.count("BEGIN:VEVENT") == 1  # the undated tournament stays out


@pytest.mark.django_db
def test_a_bad_or_dead_address_is_not_found(site, client):
    me, _ = _signup(_scrim(), "dead157@example.com", "停用157")
    good = reverse("calendar_feed", args=[calendar_feed.token(me)])
    assert client.get(good.replace(".ics", "x.ics")).status_code == 404
    me.is_active = False
    me.save(update_fields=["is_active"])
    assert client.get(good).status_code == 404


def test_text_is_escaped():
    assert calendar_feed._escape("a,b;c\\d\ne") == r"a\,b\;c\\d\ne"


def test_long_lines_are_folded_without_splitting_characters():
    line = "SUMMARY:内战：" + "很长的标题" * 12
    folded = calendar_feed._fold(line)
    pieces = folded.split("\r\n")
    assert len(pieces) > 1
    assert all(len(piece.encode()) <= 75 for piece in pieces)
    assert all(piece.startswith(" ") for piece in pieces[1:])
    assert folded.replace("\r\n ", "") == line
    assert calendar_feed._fold("VERSION:2.0") == "VERSION:2.0"


@pytest.mark.django_db
def test_my_registrations_page_offers_it(site, client):
    me, _ = _signup(_scrim(), "page157@example.com", "页面157")
    client.force_login(me)
    page = client.get(reverse("me_registrations")).content.decode()
    assert calendar_feed.feed_url(me, webcal=True) in page
    assert calendar_feed.feed_url(me) in page
    assert calendar_feed.feed_url(me, webcal=True).startswith("webcal://")


@pytest.mark.django_db
def test_hammering_the_feed_is_limited(site, client):
    me, _ = _signup(_scrim(), "busy157@example.com", "频繁157")
    from core.views import CALENDAR_RATE_LIMIT

    for _ in range(CALENDAR_RATE_LIMIT):
        assert _feed(client, me).status_code == 200
    assert _feed(client, me).status_code == 429
