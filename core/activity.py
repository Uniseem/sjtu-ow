"""「活动数据」 (design 14.2, v6.53): what the club did over a stretch of time,
for the officers' annual review and handover reports.

Activity, not visits: the site keeps no visitor statistics (19.2 #13). Only
published and finished events count; drafts and cancelled ones do not.
"""

from __future__ import annotations

import csv
import io
from dataclasses import dataclass
from datetime import date, datetime, time, timedelta

from django.core.exceptions import PermissionDenied
from django.db.models import Count, Q
from django.db.models.functions import Coalesce
from django.http import HttpResponse
from django.shortcuts import render
from django.urls import reverse
from django.utils import timezone

SCHOOL_YEAR_STARTS = (9, 1)  # 9 月 1 日
# Dates people can ask for (round 166): 9999-12-31 plus a day overflowed.
EARLIEST, LATEST = date(2000, 1, 1), date(2100, 12, 31)


@dataclass(frozen=True)
class Period:
    start: date
    end: date  # included

    @property
    def since(self) -> datetime:
        return timezone.make_aware(datetime.combine(self.start, time.min))

    @property
    def until(self) -> datetime:
        return timezone.make_aware(
            datetime.combine(self.end + timedelta(days=1), time.min)
        )


def school_year(today: date) -> Period:
    """本学年: from the last 1 September up to today."""
    month, day = SCHOOL_YEAR_STARTS
    year = today.year if (today.month, today.day) >= (month, day) else today.year - 1
    return Period(date(year, month, day), today)


def last_school_year(today: date) -> Period:
    begins = school_year(today).start
    return Period(begins.replace(year=begins.year - 1), begins - timedelta(days=1))


def recent(today: date, days: int = 30) -> Period:
    return Period(today - timedelta(days=days - 1), today)


def period_from(params, today: date) -> tuple[Period, str]:
    """The period asked for, or this school year with a word on what was wrong."""
    raw_start, raw_end = params.get("start", ""), params.get("end", "")
    if not raw_start and not raw_end:
        return school_year(today), ""
    try:
        start, end = date.fromisoformat(raw_start), date.fromisoformat(raw_end)
    except ValueError:
        return school_year(today), "日期没填全或格式不对，下面是本学年的数据。"
    if start > end:
        return school_year(today), "开始日期晚于结束日期，下面是本学年的数据。"
    if start < EARLIEST or end > LATEST:
        return school_year(
            today
        ), "日期只能在 2000 年到 2100 年之间，下面是本学年的数据。"
    return Period(start, end), ""


@dataclass(frozen=True)
class Event:
    when: datetime
    kind: str  # 内战 / 赛事
    title: str
    status: str
    entries: int  # scrims: signups; tournaments: approved teams
    players: int  # scrims: picked to play; tournaments: people on those teams
    url: str


def _scrims(period):
    from scrims.models import Scrim, ScrimStatus

    return Scrim.objects.filter(
        status__in=[ScrimStatus.PUBLISHED, ScrimStatus.FINISHED],
        starts_at__gte=period.since,
        starts_at__lt=period.until,
    )


def _tournaments(period):
    from tournaments.models import Tournament, TournamentStatus

    return (
        Tournament.objects.filter(
            status__in=[TournamentStatus.PUBLISHED, TournamentStatus.FINISHED]
        )
        .annotate(day=Coalesce("starts_at", "registration_closes_at"))
        .filter(day__gte=period.since, day__lt=period.until)
    )


def _players(tournaments):
    """Everyone on an approved roster of these tournaments."""
    from tournaments.models import RegistrationMember, RegistrationStatus

    return RegistrationMember.objects.filter(
        tournament__in=tournaments,
        is_active=True,
        registration__status=RegistrationStatus.APPROVED,
    )


def events(period: Period) -> list[Event]:
    from tournaments.models import RegistrationStatus

    rows = []
    for scrim in _scrims(period).annotate(
        entries=Count("signups"),
        players=Count("signups", filter=Q(signups__is_selected=True)),
    ):
        rows.append(
            Event(
                scrim.starts_at,
                "内战",
                scrim.title,
                scrim.get_status_display(),
                scrim.entries,
                scrim.players,
                reverse("scrims:edit", args=[scrim.pk]),
            )
        )
    tournaments = _tournaments(period).annotate(
        entries=Count(
            "registrations",
            filter=Q(registrations__status=RegistrationStatus.APPROVED),
            distinct=True,
        )
    )
    players = dict(
        _players(tournaments)
        .values("tournament")
        .annotate(people=Count("user", distinct=True))
        .values_list("tournament", "people")
    )
    for tournament in tournaments:
        rows.append(
            Event(
                tournament.day,
                "赛事",
                tournament.title,
                tournament.get_status_display(),
                tournament.entries,
                players.get(tournament.pk, 0),
                reverse("tournaments:edit", args=[tournament.pk]),
            )
        )
    rows.sort(key=lambda row: row.when)
    return rows


def summary(period: Period, rows: list[Event]) -> dict:
    from comments.models import Comment
    from content.models import ArticlePage
    from members.services import joined_users
    from scrims.models import ScrimSignup
    from teams.models import Team

    newcomers = joined_users().filter(
        date_joined__gte=period.since, date_joined__lt=period.until
    )
    scrims = [row for row in rows if row.kind == "内战"]
    tournaments = [row for row in rows if row.kind == "赛事"]
    return {
        "members": newcomers.count(),
        "sjtu_members": newcomers.filter(is_sjtu=True).count(),
        "scrims": len(scrims),
        "scrim_signups": sum(row.entries for row in scrims),
        "scrim_players": sum(row.players for row in scrims),
        "scrim_people": ScrimSignup.objects.filter(scrim__in=_scrims(period))
        .values("user")
        .distinct()
        .count(),
        "tournaments": len(tournaments),
        "tournament_teams": sum(row.entries for row in tournaments),
        "tournament_people": _players(_tournaments(period))
        .values("user")
        .distinct()
        .count(),
        "articles": ArticlePage.objects.live()
        .filter(
            first_published_at__gte=period.since, first_published_at__lt=period.until
        )
        .count(),
        "comments": Comment.objects.filter(
            created_at__gte=period.since,
            created_at__lt=period.until,
            is_hidden=False,
            is_deleted=False,
        ).count(),
        "teams": Team.objects.filter(
            created_at__gte=period.since, created_at__lt=period.until
        ).count(),
    }


def csv_text(rows: list[Event]) -> str:
    out = io.StringIO()
    out.write("﻿")  # BOM so Excel reads UTF-8
    writer = csv.writer(out)
    writer.writerow(
        ["日期", "类型", "标题", "状态", "报名人次或队伍", "上场或参赛人数"]
    )
    for row in rows:
        writer.writerow(
            [
                f"{timezone.localtime(row.when):%Y-%m-%d %H:%M}",
                row.kind,
                row.title,
                row.status,
                row.entries,
                row.players,
            ]
        )
    return out.getvalue()


def can_view(user) -> bool:
    """The officers: the same people the 后台手册 has a part for, less the
    certified authors."""
    from accounts.services import GROUP_CONTENT
    from scrims import services as scrim_services
    from tournaments import services as tournament_services

    if not getattr(user, "is_authenticated", False):
        return False
    return (
        user.is_superuser
        or user.groups.filter(name=GROUP_CONTENT).exists()
        or tournament_services.can_manage(user)
        or scrim_services.can_manage(user)
    )


def activity_view(request):
    if not can_view(request.user):
        raise PermissionDenied("活动数据给社团干部看。")
    today = timezone.localdate()
    period, error = period_from(request.GET, today)
    rows = events(period)
    if request.GET.get("format") == "csv":
        response = HttpResponse(csv_text(rows), content_type="text/csv; charset=utf-8")
        response["Content-Disposition"] = (
            f'attachment; filename="activity-{period.start}-{period.end}.csv"'
        )
        return response
    presets = [
        ("本学年", school_year(today)),
        ("上学年", last_school_year(today)),
        ("近 30 天", recent(today)),
    ]
    return render(
        request,
        "core/admin/activity.html",
        {
            "page_title": "活动数据",
            "period": period,
            "error": error,
            "presets": presets,
            "rows": rows,
            "totals": summary(period, rows),
        },
    )
