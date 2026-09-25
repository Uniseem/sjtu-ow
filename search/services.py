"""Site search (design 13.16): substring matching over four kinds of content.

No tokeniser: every term must occur somewhere in the text, case-folded.
Article bodies are StreamFields whose JSON escapes Chinese, so all matching
is done in Python on rendered text rather than in SQL. The club's data is
small enough for that (13.16 says when to revisit).
"""

from __future__ import annotations

from dataclasses import dataclass, field

from django.utils.html import strip_tags

PER_TYPE_LIMIT = 20
MAX_QUERY_LENGTH = 50
MAX_TERMS = 5
EXCERPT_RADIUS = 40


@dataclass
class Hit:
    title: str
    url: str
    excerpt: str
    meta: str = ""


@dataclass
class Group:
    key: str
    label: str
    hits: list = field(default_factory=list)
    truncated: bool = False


def parse_query(raw: str | None) -> list[str]:
    """Up to MAX_TERMS case-folded words from at most MAX_QUERY_LENGTH chars."""
    text = (raw or "").strip()[:MAX_QUERY_LENGTH]
    terms = [term.casefold() for term in text.split() if term]
    return terms[:MAX_TERMS]


def plain(text) -> str:
    return " ".join(strip_tags(str(text or "")).split())


def matches(text: str, terms: list[str]) -> bool:
    folded = text.casefold()
    return bool(terms) and all(term in folded for term in terms)


def excerpt(text: str, terms: list[str]) -> str:
    """About EXCERPT_RADIUS characters either side of the first hit."""
    text = plain(text)
    folded = text.casefold()
    positions = [folded.find(term) for term in terms]
    positions = [position for position in positions if position >= 0]
    if not positions:
        cut = text[: 2 * EXCERPT_RADIUS]
        return cut + ("…" if len(text) > len(cut) else "")
    first = min(positions)
    start = max(first - EXCERPT_RADIUS, 0)
    end = min(first + EXCERPT_RADIUS, len(text))
    return (
        ("…" if start > 0 else "") + text[start:end] + ("…" if end < len(text) else "")
    )


def _gather(rows, terms, text_of, hit_of) -> tuple[list[Hit], bool]:
    """Walk rows in order; stop once PER_TYPE_LIMIT + 1 matched."""
    hits = []
    for row in rows:
        text = text_of(row)
        if not matches(text, terms):
            continue
        hits.append(hit_of(row, text))
        if len(hits) > PER_TYPE_LIMIT:
            return hits[:PER_TYPE_LIMIT], True
    return hits, False


def search_articles(terms) -> Group:
    from content.models import ArticlePage

    pages = (
        ArticlePage.objects.live()
        .public()
        .specific()
        .select_related("category")
        .order_by("-last_published_at", "-pk")
    )

    def text_of(page):
        return f"{page.title}\n{page.summary}\n{plain(page.body)}"

    def hit_of(page, text):
        return Hit(
            title=page.title,
            url=page.get_url() or "",
            excerpt=excerpt(text, terms),
            meta=page.category.name if page.category_id else "文章",
        )

    hits, truncated = _gather(pages, terms, text_of, hit_of)
    return Group("articles", "文章", hits, truncated)


def search_events(terms) -> Group:
    from scrims.models import Scrim, ScrimStatus
    from tournaments.models import Tournament, TournamentStatus

    tournaments = Tournament.objects.filter(
        status__in=[TournamentStatus.PUBLISHED, TournamentStatus.FINISHED]
    ).order_by("-updated_at", "-pk")
    scrims = Scrim.objects.filter(
        status__in=[ScrimStatus.PUBLISHED, ScrimStatus.FINISHED]
    ).order_by("-updated_at", "-pk")

    rows = [("赛事", row) for row in tournaments] + [("内战", row) for row in scrims]

    def text_of(item):
        _kind, row = item
        summary = getattr(row, "summary", "")
        return f"{row.title}\n{summary}\n{plain(row.description)}"

    def hit_of(item, text):
        kind, row = item
        url = row.get_absolute_url() if kind == "赛事" else f"/scrims/{row.pk}/"
        return Hit(
            title=row.title,
            url=url,
            excerpt=excerpt(text, terms),
            meta=kind,
        )

    hits, truncated = _gather(rows, terms, text_of, hit_of)
    return Group("events", "赛事与内战", hits, truncated)


def search_teams(terms) -> Group:
    from teams.models import Team

    teams = Team.objects.filter(disbanded_at__isnull=True).order_by(
        "-updated_at", "-pk"
    )

    def text_of(team):
        return f"{team.name}\n{team.description}"

    def hit_of(team, text):
        return Hit(
            title=team.name,
            url=team.get_absolute_url(),
            excerpt=excerpt(team.description, terms),
            meta="招募中" if team.is_recruiting else "战队",
        )

    hits, truncated = _gather(teams, terms, text_of, hit_of)
    return Group("teams", "战队", hits, truncated)


def search_members(terms) -> Group:
    from members.services import joined_users

    users = joined_users().order_by("nickname", "pk")

    def hit_of(user, _text):
        return Hit(title=user.nickname, url="/members/", excerpt="", meta="成员")

    hits, truncated = _gather(users, terms, lambda user: user.nickname, hit_of)
    return Group("members", "成员", hits, truncated)


def search_all(terms) -> list[Group]:
    return [
        search_articles(terms),
        search_events(terms),
        search_teams(terms),
        search_members(terms),
    ]
