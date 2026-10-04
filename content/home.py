"""Data for the homepage (design 5.2, v4.0 in round 086).

Top to bottom: the hero picture, the figures row, 近期 (the latest tournament
and the next scrims, v6.66), 资讯 with 公告 beside it, then 战队.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date

from django.utils import timezone

LATEST_ARTICLE_COUNT = 4
SCRIM_ROW_COUNT = 5
NOTICE_COUNT = 5
NOTICE_CATEGORIES = ("notice", "event-notice")
HOME_TEAM_COUNT = 6


def news_list(pinned=(), limit: int = LATEST_ARTICLE_COUNT):
    """Pinned articles first (design 5.2), then the latest, without repeats."""
    from content.models import ArticlePage

    items = list(pinned)[:limit]
    seen = {article.pk for article in items}
    from accounts.services import with_avatars

    latest = (
        with_avatars(ArticlePage.objects.live().public(), "author__")
        .select_related("category", "cover", "author")
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
    """近期's big card: the latest tournament, its phase and approved teams."""

    tournament: object
    approved: int = 0
    phase: str = "open"


def _when(tournament):
    return tournament.starts_at or tournament.registration_opens_at


def feature_tournament(tournaments, now=None) -> Feature | None:
    """近期's big card (design 5.2, v6.66): the latest tournament. One taking
    registrations (closing soonest), else the next one not yet over (the
    soonest), else the one that ended last; nothing only when there is none.
    Until round 188 the card showed only while registration was open."""
    from tournaments.services import approved_counts

    now = now or timezone.now()
    by_phase = {}
    for item in tournaments:
        by_phase.setdefault(item.phase(now), []).append(item)
    if by_phase.get("open"):
        chosen = min(by_phase["open"], key=lambda item: item.registration_closes_at)
    elif by_phase.get("upcoming") or by_phase.get("closed"):
        ahead = by_phase.get("upcoming", []) + by_phase.get("closed", [])
        chosen = min(ahead, key=_when)
    elif by_phase.get("finished"):
        chosen = max(by_phase["finished"], key=_when)
    else:
        return None
    return Feature(
        chosen, approved_counts([chosen]).get(chosen.pk, 0), chosen.phase(now)
    )


def home_tournaments():
    """The ones feature_tournament chooses from: everything published, and
    the finished one that ended last (older ones can never be chosen)."""
    from tournaments.models import Tournament, TournamentStatus

    published = Tournament.objects.filter(status=TournamentStatus.PUBLISHED)
    last = (
        Tournament.objects.filter(status=TournamentStatus.FINISHED)
        .order_by("-starts_at", "-registration_opens_at")
        .first()
    )
    found = list(published.select_related("cover"))
    return found + ([last] if last else [])


@dataclass
class ScrimRow:
    """One scrim in 近期: sign-ups against the players one game needs."""

    scrim: object
    count: int = 0
    capacity: int = 0


def scrim_rows(scrims, limit: int = SCRIM_ROW_COUNT) -> list[ScrimRow]:
    """The next scrims, earliest first, with sign-ups / needed (design 5.2)."""
    from scrims.services import signup_totals

    chosen = sorted(scrims, key=lambda item: item.starts_at)[:limit]
    totals = signup_totals(chosen)
    return [
        ScrimRow(item, totals.get(item.pk, 0), item.players_needed) for item in chosen
    ]


def blanks(items, size: int) -> range:
    """Empty places that keep a homepage block its size (design 5.2, v6.66)."""
    return range(max(0, size - len(items)))


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

    site = SiteSettings.load()
    rows = scrim_rows(upcoming_scrims())
    news = news_list(pinned)
    notice_rows = notices()
    home_teams = teams()
    return {
        "hero_image": site.hero_image,
        "qq_group_url": site.qq_group_url,
        "member_count": member_count(),
        "team_count": team_count(),
        "scrims_held": scrims_held(),
        "age": community_age(site.founded_on),
        "feature": feature_tournament(home_tournaments()),
        "scrim_rows": rows,
        "scrim_blanks": blanks(rows, SCRIM_ROW_COUNT),
        "news": news,
        "news_blanks": blanks(news, LATEST_ARTICLE_COUNT),
        "pinned_ids": {article.pk for article in pinned},
        "notices": notice_rows,
        "notice_blanks": blanks(notice_rows, NOTICE_COUNT),
        "home_teams": home_teams,
        "team_blanks": blanks(home_teams, HOME_TEAM_COUNT),
    }
