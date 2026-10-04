"""Round 162: 「活动数据」 for the officers (design 14.2, v6.53)."""

import csv
import io
from datetime import date, datetime, timedelta

import pytest
from allauth.account.models import EmailAddress
from django.core.management import call_command
from django.urls import reverse
from django.utils import timezone

from accounts.models import User
from accounts.tests.test_onboarding import _user
from comments.models import Comment
from core import activity
from core.tests.test_prerender import _article
from scrims.models import Scrim, ScrimSignup, ScrimStatus
from scrims.tests.test_scrims import make_user
from teams.models import Team
from tournaments.models import (
    Registration,
    RegistrationMember,
    RegistrationStatus,
    Tournament,
    TournamentStatus,
)

MARCH = activity.Period(date(2026, 3, 1), date(2026, 3, 31))


def _at(*args):
    return timezone.make_aware(datetime(*args))


@pytest.fixture
def site(db):
    call_command("init_site", verbosity=0)


def _member(email, nickname, joined, *, sjtu=True, verified=True):
    user = make_user(email, nickname, sjtu=sjtu)
    EmailAddress.objects.create(user=user, email=email, verified=verified, primary=True)
    User.objects.filter(pk=user.pk).update(date_joined=joined)
    return user


def _scrim(title, starts_at, status=ScrimStatus.FINISHED):
    return Scrim.objects.create(title=title, starts_at=starts_at, status=status)


def _signup(scrim, user, *, picked):
    ScrimSignup.objects.create(
        scrim=scrim,
        user=user,
        game_account=user.game_accounts.first(),
        role_damage=True,
        is_selected=picked,
    )


def _roster(tournament, users, status):
    registration = Registration.objects.create(
        tournament=tournament,
        status=status,
        team_name=f"{tournament.title}队{status}",
        submitted_by=users[0],
    )
    for user in users:
        RegistrationMember.objects.create(
            registration=registration,
            tournament=tournament,
            user=user,
            game_account=user.game_accounts.first(),
            nickname=user.nickname,
            battletag=user.game_accounts.first().battletag,
        )


def _cup(title, *, starts_at=None, closes=None, status=TournamentStatus.FINISHED):
    closes = closes or _at(2026, 2, 1)
    return Tournament.objects.create(
        title=title,
        registration_opens_at=closes - timedelta(days=7),
        registration_closes_at=closes,
        starts_at=starts_at,
        roster_min=2,
        roster_max=5,
        status=status,
    )


@pytest.fixture
def march(site):
    """A month of club life, with something just outside on every side."""
    a = _member("a162@example.com", "甲162", _at(2026, 3, 2))
    b = _member("b162@example.com", "乙162", _at(2026, 3, 31, 23, 0), sjtu=False)
    c = _member("c162@example.com", "丙162", _at(2026, 2, 27))
    _member("d162@example.com", "丁162", _at(2026, 3, 5), verified=False)

    first = _scrim("三月第一场", _at(2026, 3, 10, 19))
    _signup(first, a, picked=True)
    _signup(first, b, picked=False)
    last = _scrim("月底那场", _at(2026, 3, 31, 23, 30), ScrimStatus.PUBLISHED)
    _signup(last, a, picked=True)
    _signup(_scrim("取消了", _at(2026, 3, 12), ScrimStatus.CANCELLED), c, picked=True)
    _scrim("还是草稿", _at(2026, 3, 13), ScrimStatus.DRAFT)
    _signup(_scrim("四月的", _at(2026, 4, 1, 0, 0)), c, picked=True)

    cup = _cup("三月杯", starts_at=_at(2026, 3, 20, 14))
    _roster(cup, [a, b], RegistrationStatus.APPROVED)
    _roster(cup, [c], RegistrationStatus.REJECTED)
    undated = _cup(
        "没定时间的杯", closes=_at(2026, 3, 15), status=TournamentStatus.PUBLISHED
    )
    _roster(undated, [a], RegistrationStatus.APPROVED)  # 甲 plays twice
    _cup("取消的杯", starts_at=_at(2026, 3, 21), status=TournamentStatus.CANCELLED)

    # _article writes as the superuser, or makes the same author every time.
    User.objects.create_superuser(
        email="root162@example.com",
        password="Correct-Horse-Battery-1",
        nickname="站长162",
        agreed_terms_at=timezone.now(),
        agreed_cross_border_at=timezone.now(),
    )
    article = _article(title="三月的文章", slug="march-162")
    type(article).objects.filter(pk=article.pk).update(
        first_published_at=_at(2026, 3, 8)
    )
    old = _article(title="二月的文章", slug="feb-162")
    type(old).objects.filter(pk=old.pk).update(first_published_at=_at(2026, 2, 8))
    for when, extra in (
        (_at(2026, 3, 9), {}),
        (_at(2026, 3, 9), {"is_hidden": True}),
        (_at(2026, 3, 9), {"is_deleted": True}),
        (_at(2026, 2, 9), {}),
    ):
        comment = Comment.objects.create(page=article, author=a, body="好", **extra)
        Comment.objects.filter(pk=comment.pk).update(created_at=when)

    for name, when in (("三月队", _at(2026, 3, 3)), ("二月队", _at(2026, 2, 3))):
        team = Team.objects.create(name=name)
        Team.objects.filter(pk=team.pk).update(created_at=when)


@pytest.mark.django_db
def test_the_months_numbers(march):
    rows = activity.events(MARCH)
    assert [(row.kind, row.title) for row in rows] == [
        ("内战", "三月第一场"),
        ("赛事", "没定时间的杯"),  # by its signup deadline
        ("赛事", "三月杯"),
        ("内战", "月底那场"),
    ]
    by_title = {row.title: row for row in rows}
    assert (by_title["三月第一场"].entries, by_title["三月第一场"].players) == (2, 1)
    assert (by_title["三月杯"].entries, by_title["三月杯"].players) == (1, 2)

    totals = activity.summary(MARCH, rows)
    assert totals == {
        "members": 2,
        "sjtu_members": 1,
        "scrims": 2,
        "scrim_signups": 3,
        "scrim_players": 2,
        "scrim_people": 2,
        "tournaments": 2,
        "tournament_teams": 2,
        "tournament_people": 2,
        "articles": 1,
        "comments": 1,
        "teams": 1,
    }


def test_the_periods():
    assert activity.school_year(date(2026, 10, 4)) == activity.Period(
        date(2026, 9, 1), date(2026, 10, 4)
    )
    assert activity.school_year(date(2026, 8, 31)).start == date(2025, 9, 1)
    assert activity.school_year(date(2026, 9, 1)).start == date(2026, 9, 1)
    assert activity.last_school_year(date(2026, 10, 4)) == activity.Period(
        date(2025, 9, 1), date(2026, 8, 31)
    )
    assert activity.recent(date(2026, 10, 4)).start == date(2026, 9, 5)
    today = date(2026, 10, 4)
    assert activity.period_from({}, today) == (activity.school_year(today), "")
    assert activity.period_from(
        {"start": "2026-03-01", "end": "2026-03-31"}, today
    ) == (
        MARCH,
        "",
    )
    for wrong in (
        {"start": "2026-03-01"},
        {"start": "2026-04-01", "end": "2026-03-01"},
    ):
        period, error = activity.period_from(wrong, today)
        assert period == activity.school_year(today) and error


@pytest.mark.django_db
def test_officers_see_it_and_can_take_the_table_away(march, client):
    manager = _user("s162@example.com", "内战管理员", "投稿者")
    client.force_login(manager)
    menu = client.get(reverse("backoffice:home")).content.decode()
    assert reverse("admin_activity") in menu

    page = client.get(
        reverse("admin_activity"), {"start": "2026-03-01", "end": "2026-03-31"}
    )
    html = page.content.decode()
    assert page.status_code == 200
    assert html.count("<tr data-activity-event>") == 4
    assert "<dt>内战</dt><dd>2 场 · 报名 3 人次 · 上场 2 人次 · 参与 2 人</dd>" in html

    download = client.get(
        reverse("admin_activity"),
        {"start": "2026-03-01", "end": "2026-03-31", "format": "csv"},
    )
    text = download.content.decode("utf-8")
    assert text.startswith("﻿")
    table = list(csv.reader(io.StringIO(text.lstrip("﻿"))))
    assert table[0][0] == "日期" and len(table) == 5
    assert table[3][1:] == ["赛事", "三月杯", "已结束", "1", "2"]


@pytest.mark.django_db
def test_writers_do_not(site, client):
    for user in (
        _user("w162@example.com", "投稿者"),
        _user("a162w@example.com", "认证作者", "投稿者"),
    ):
        client.force_login(user)
        assert client.get(reverse("admin_activity")).status_code != 200
        menu = client.get(reverse("backoffice:home")).content.decode()
        assert reverse("admin_activity") not in menu
