"""Data for the homepage blocks (design 5.2, v2.0 redesign in round 075).

Top to bottom: the lead (焦点图 + 近期), 01 资讯, 02 赛事与内战 (a 14-day
strip, tournaments, scrims), 03 战队, 04 参与.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, timedelta

from django.utils import timezone

CAROUSEL_FALLBACK = 5
LATEST_ARTICLE_COUNT = 6
NEXT_UP_COUNT = 4
STRIP_DAYS = 14
ARENA_TOURNAMENT_COUNT = 3
HOME_TEAM_COUNT = 6


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


@dataclass
class Agenda:
    """One entry of 近期: what it is, the date on its stub, and the stub label."""

    kind: str  # "tournament" | "scrim"
    item: object
    moment: object
    label: str


def next_up(tournaments, scrims, limit: int = NEXT_UP_COUNT) -> list[Agenda]:
    """Open tournaments by deadline and this week's scrims by start, merged by date."""
    entries = [
        Agenda("tournament", item, item.registration_closes_at, "截止")
        for item in tournaments
    ]
    entries += [Agenda("scrim", item, item.starts_at, "开始") for item in scrims]
    entries.sort(key=lambda entry: entry.moment)
    return entries[:limit]


@dataclass
class Day:
    date: date
    is_today: bool
    scrims: list = field(default_factory=list)
    tournaments: list = field(default_factory=list)

    @property
    def count(self) -> int:
        return len(self.scrims) + len(self.tournaments)

    @property
    def first_url(self) -> str:
        if self.scrims:
            return f"/scrims/{self.scrims[0].pk}/"
        if self.tournaments:
            return self.tournaments[0].get_absolute_url()
        return ""


def day_strip(today: date | None = None, days: int = STRIP_DAYS) -> list[Day]:
    """From today, one cell a day: public or finished scrims, tournaments that start.

    The homepage is prerendered and rebuilt every night, so 「今天」 stays right.
    """
    from scrims.models import Scrim, ScrimStatus
    from tournaments.models import Tournament, TournamentStatus

    today = today or timezone.localdate()
    last = today + timedelta(days=days - 1)
    cells = [Day(today + timedelta(days=offset), offset == 0) for offset in range(days)]
    by_date = {cell.date: cell for cell in cells}
    scrims = Scrim.objects.filter(
        status__in=[ScrimStatus.PUBLISHED, ScrimStatus.FINISHED],
        starts_at__date__gte=today,
        starts_at__date__lte=last,
    ).order_by("starts_at")
    for scrim in scrims:
        by_date[timezone.localdate(scrim.starts_at)].scrims.append(scrim)
    tournaments = Tournament.objects.filter(
        status__in=[TournamentStatus.PUBLISHED, TournamentStatus.FINISHED],
        starts_at__date__gte=today,
        starts_at__date__lte=last,
    ).order_by("starts_at")
    for tournament in tournaments:
        by_date[timezone.localdate(tournament.starts_at)].tournaments.append(tournament)
    return cells


def strip_scrims(cells) -> list:
    """The scrims in the strip that have not started yet, for the list beside it."""
    from scrims.models import ScrimStatus

    now = timezone.now()
    return [
        scrim
        for cell in cells
        for scrim in cell.scrims
        if scrim.status == ScrimStatus.PUBLISHED and scrim.starts_at >= now
    ]


def arena_tournaments(limit: int = ARENA_TOURNAMENT_COUNT) -> list[tuple[str, object]]:
    """Taking registrations first (by deadline), then opening soon (by opening)."""
    from tournaments.services import grouped_tournaments

    groups = {phase: items for phase, _label, items in grouped_tournaments()}
    items = [("open", item) for item in groups["open"]]
    items += [("upcoming", item) for item in groups["upcoming"]]
    return items[:limit]


def approved_counts(tournaments) -> dict:
    from tournaments.services import approved_counts

    return approved_counts(tournaments)


def signup_counts(scrims) -> dict:
    from scrims.services import signup_totals

    return signup_totals(scrims)


def teams(limit: int = HOME_TEAM_COUNT):
    from django.db.models import Count

    from teams import services

    return list(
        services.active_teams()
        .select_related("logo")
        .annotate(member_count=Count("memberships"))
        .order_by("-created_at")[:limit]
    )


def member_count() -> int:
    from members.services import joined_users

    return joined_users().count()
