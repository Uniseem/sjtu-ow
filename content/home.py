"""Data for the homepage (design 5.2, v3.0 in round 082).

Top to bottom: the full-screen hero (key figures, 近期安排, quick entries),
资讯 with 通知公告 and 活动统计 beside it, then 战队.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date

from django.utils import timezone

LATEST_ARTICLE_COUNT = 6
NEXT_UP_COUNT = 4
NOTICE_COUNT = 5
NOTICE_CATEGORIES = ("notice", "event-notice")
HOME_TEAM_COUNT = 6


def news_list(pinned=(), limit: int = LATEST_ARTICLE_COUNT):
    """Pinned articles first (design 5.2), then the latest, without repeats."""
    from content.models import ArticlePage

    items = list(pinned)[:limit]
    seen = {article.pk for article in items}
    latest = (
        ArticlePage.objects.live()
        .public()
        .select_related("category", "cover")
        .order_by("-first_published_at", "-last_published_at")[: limit + len(seen)]
    )
    items += [article for article in latest if article.pk not in seen]
    return items[:limit]


def notices(limit: int = NOTICE_COUNT):
    """The latest 公告 and 赛事通知 (design 5.2 通知公告)."""
    from content.models import ArticlePage

    return list(
        ArticlePage.objects.live()
        .public()
        .filter(category__slug__in=NOTICE_CATEGORIES)
        .select_related("category")
        .order_by("-first_published_at", "-last_published_at")[:limit]
    )


@dataclass
class Agenda:
    """One entry of 近期安排: what it is, the date on its block, and progress."""

    kind: str  # "tournament" | "scrim"
    item: object
    moment: object
    label: str
    count: int = 0
    capacity: int = 0  # scrims only; tournaments have no team cap (5.2)


def next_up(tournaments, scrims, limit: int = NEXT_UP_COUNT) -> list[Agenda]:
    """Open tournaments by deadline and this week's scrims by start, merged by date."""
    entries = [
        Agenda("tournament", item, item.registration_closes_at, "截止")
        for item in tournaments
    ]
    entries += [Agenda("scrim", item, item.starts_at, "开始") for item in scrims]
    entries.sort(key=lambda entry: entry.moment)
    return entries[:limit]


def agenda(tournaments, scrims, limit: int = NEXT_UP_COUNT) -> list[Agenda]:
    """next_up with the numbers the card shows: approved teams, sign-ups / needed."""
    from scrims.services import signup_totals
    from tournaments.services import approved_counts

    entries = next_up(tournaments, scrims, limit)
    approved = approved_counts([e.item for e in entries if e.kind == "tournament"])
    signups = signup_totals([e.item for e in entries if e.kind == "scrim"])
    for entry in entries:
        if entry.kind == "tournament":
            entry.count = approved.get(entry.item.pk, 0)
        else:
            entry.count = signups.get(entry.item.pk, 0)
            entry.capacity = entry.item.players_needed
    return entries


@dataclass
class Age:
    years: int
    days: int


def _anniversary(founded: date, year: int) -> date:
    try:
        return founded.replace(year=year)
    except ValueError:  # 29 February in a common year
        return founded.replace(year=year, day=28)


def community_age(founded: date | None, today: date | None = None) -> Age | None:
    """「社区已成立 N 年 M 天」 from the founding date (design 5.2).

    None when the date is not set or lies in the future: the hero then leaves
    the figure out rather than print something wrong.
    """
    if founded is None:
        return None
    today = today or timezone.localdate()
    if founded > today:
        return None
    years = today.year - founded.year
    if _anniversary(founded, today.year) > today:
        years -= 1
    last = _anniversary(founded, founded.year + years)
    return Age(years=years, days=(today - last).days)


def activity_stats() -> dict:
    """活动统计 (design 5.2): scrims held and tournaments run, both finished."""
    from scrims.models import Scrim, ScrimStatus
    from tournaments.models import Tournament, TournamentStatus

    return {
        "scrims": Scrim.objects.filter(status=ScrimStatus.FINISHED).count(),
        "tournaments": Tournament.objects.filter(
            status=TournamentStatus.FINISHED
        ).count(),
    }


def teams(limit: int = HOME_TEAM_COUNT):
    from django.db.models import Count

    from teams import services

    return list(
        services.active_teams()
        .select_related("logo")
        .annotate(member_count=Count("memberships"))
        .order_by("-created_at")[:limit]
    )


def team_count() -> int:
    from teams import services

    return services.active_teams().count()


def member_count() -> int:
    from members.services import joined_users

    return joined_users().count()


def homepage(pinned) -> dict:
    """Everything home_page.html needs, in one place."""
    from content.models import ArticleCategory
    from core.models import SiteSettings
    from scrims.services import upcoming_scrims
    from tournaments.services import open_tournaments

    site = SiteSettings.load()
    news = news_list(pinned)
    return {
        "member_count": member_count(),
        "team_count": team_count(),
        "age": community_age(site.founded_on),
        "agenda": agenda(open_tournaments(), upcoming_scrims()),
        "news_lead": news[0] if news else None,
        "news_rest": news[1:],
        "pinned_ids": {article.pk for article in pinned},
        "categories": ArticleCategory.objects.all(),
        "notices": notices(),
        "stats": activity_stats(),
        "home_teams": teams(),
        "qq_group_url": site.qq_group_url,
    }
