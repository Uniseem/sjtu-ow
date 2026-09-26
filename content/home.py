"""Data for the homepage (design 5.2, v4.0 in round 086).

Top to bottom: the hero picture, the figures row, 近期 (the open tournament
and this week's scrims), 资讯 with 公告 beside it, then 战队.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date

from django.utils import timezone

LATEST_ARTICLE_COUNT = 4
SCRIM_ROW_COUNT = 4
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
class Feature:
    """The open tournament that closes soonest, with its approved teams."""

    tournament: object
    approved: int = 0


def feature_tournament(tournaments) -> Feature | None:
    """近期's big card (design 5.2): only the one closing soonest, or nothing."""
    from tournaments.services import approved_counts

    if not tournaments:
        return None
    first = min(tournaments, key=lambda item: item.registration_closes_at)
    return Feature(first, approved_counts([first]).get(first.pk, 0))


@dataclass
class ScrimRow:
    """One scrim in 近期: sign-ups against the players one game needs."""

    scrim: object
    count: int = 0
    capacity: int = 0


def scrim_rows(scrims, limit: int = SCRIM_ROW_COUNT) -> list[ScrimRow]:
    """This week's scrims, earliest first, with sign-ups / needed (design 5.2)."""
    from scrims.services import signup_totals

    chosen = sorted(scrims, key=lambda item: item.starts_at)[:limit]
    totals = signup_totals(chosen)
    return [
        ScrimRow(item, totals.get(item.pk, 0), item.players_needed) for item in chosen
    ]


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


def scrims_held() -> int:
    """累计内战 on the figures row (design 5.2): finished scrims."""
    from scrims.models import Scrim, ScrimStatus

    return Scrim.objects.filter(status=ScrimStatus.FINISHED).count()


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
    from core.models import SiteSettings
    from scrims.services import upcoming_scrims
    from tournaments.services import open_tournaments

    site = SiteSettings.load()
    return {
        "hero_image": site.hero_image,
        "qq_group_url": site.qq_group_url,
        "member_count": member_count(),
        "team_count": team_count(),
        "scrims_held": scrims_held(),
        "age": community_age(site.founded_on),
        "feature": feature_tournament(open_tournaments()),
        "scrim_rows": scrim_rows(upcoming_scrims()),
        "news": news_list(pinned),
        "pinned_ids": {article.pk for article in pinned},
        "notices": notices(),
        "home_teams": teams(),
    }
