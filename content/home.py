"""Data for the homepage sections added in round 065 (design 5.2).

The layout follows www.sjtu.edu.cn: a photo carousel, four photo news cards,
news lists, event cards beside a calendar, and team cards.
"""

from __future__ import annotations

import calendar
from dataclasses import dataclass
from datetime import date

from django.utils import timezone

CAROUSEL_FALLBACK = 5
PICTURE_NEWS_COUNT = 4
LATEST_ARTICLE_COUNT = 7
HOME_TEAM_COUNT = 5
EVENT_CARD_COUNT = 3


@dataclass
class Slide:
    image: object
    title: str
    url: str


def _articles_with_cover():
    from content.models import ArticlePage

    return (
        ArticlePage.objects.live()
        .public()
        .filter(cover__isnull=False)
        .select_related("cover", "category")
        .order_by("-first_published_at", "-last_published_at")
    )


def carousel_slides(home) -> list[Slide]:
    """The admin's 焦点图; without any, the latest articles that have a cover."""
    items = [
        Slide(item.image, item.title, item.url)
        for item in home.carousel_items.select_related("image", "link_page")
    ]
    if items:
        return items
    return [
        Slide(article.cover, article.title, article.url)
        for article in _articles_with_cover()[:CAROUSEL_FALLBACK]
    ]


def picture_news(limit: int = PICTURE_NEWS_COUNT):
    return list(_articles_with_cover()[:limit])


def news_list(pinned=(), limit: int = LATEST_ARTICLE_COUNT):
    """Pinned articles first (design 5.2), then the latest, without repeats."""
    from content.models import ArticlePage

    items = list(pinned)[:limit]
    seen = {article.pk for article in items}
    latest = (
        ArticlePage.objects.live()
        .public()
        .select_related("category")
        .order_by("-first_published_at", "-last_published_at")[: limit + len(seen)]
    )
    items += [article for article in latest if article.pk not in seen]
    return items[:limit]


@dataclass
class Day:
    day: int
    in_month: bool
    has_event: bool
    is_today: bool


def scrim_calendar(today: date | None = None) -> dict:
    """This month's grid, Monday first, with days that have a public scrim marked.

    The homepage is prerendered and rebuilt every night, so 「今天」 stays right.
    """
    from scrims.models import Scrim, ScrimStatus

    today = today or timezone.localdate()
    first = today.replace(day=1)
    last = today.replace(day=calendar.monthrange(today.year, today.month)[1])
    starts = Scrim.objects.filter(
        status__in=[ScrimStatus.PUBLISHED, ScrimStatus.FINISHED],
        starts_at__date__gte=first,
        starts_at__date__lte=last,
    ).values_list("starts_at", flat=True)
    event_days = {timezone.localtime(moment).day for moment in starts}
    weeks = []
    for week in calendar.Calendar(firstweekday=0).monthdayscalendar(
        today.year, today.month
    ):
        weeks.append(
            [
                Day(
                    day=number,
                    in_month=number != 0,
                    has_event=number in event_days,
                    is_today=number == today.day,
                )
                for number in week
            ]
        )
    return {"year": today.year, "month": today.month, "weeks": weeks}


def teams(limit: int = HOME_TEAM_COUNT):
    from teams import services

    return list(
        services.active_teams().select_related("logo").order_by("-created_at")[:limit]
    )


def event_cards(tournaments, scrims, limit: int = EVENT_CARD_COUNT):
    """Open tournaments first, then upcoming scrims: one row of cards."""
    cards = [("tournament", item) for item in tournaments]
    cards += [("scrim", item) for item in scrims]
    return cards[:limit]
