"""Bilibili-only embed finder (design 5.2)."""

from __future__ import annotations

import re
from datetime import timedelta
from urllib.error import URLError
from urllib.parse import parse_qs, urlparse
from urllib.request import Request, urlopen

from django.utils import timezone
from wagtail.embeds.exceptions import EmbedNotFoundException
from wagtail.embeds.finders.base import EmbedFinder

BV_RE = re.compile(r"(BV[0-9A-Za-z]+)")
BILIBILI_HOSTS = frozenset(
    {
        "bilibili.com",
        "www.bilibili.com",
        "m.bilibili.com",
        "player.bilibili.com",
    }
)
B23_HOSTS = frozenset({"b23.tv", "www.b23.tv"})
PLAYER_BASE = "https://player.bilibili.com/player.html"
_USER_AGENT = "sjtu-ow-embed/1.0"
# A lookup that found nothing is remembered for this long, then retried
# (design 5.2, v7.14); a found one is kept forever (no cache_until).
FAILED_LOOKUP_TTL = timedelta(hours=1)


def _hostname(url: str) -> str:
    return (urlparse(url).hostname or "").lower()


def extract_bvid_and_page(url: str) -> tuple[str | None, int | None]:
    parsed = urlparse(url)
    query = parse_qs(parsed.query)
    bvid = (query.get("bvid") or [None])[0]
    # A query parameter is only a BV number if it looks exactly like one;
    # anything else would be carried into the player address (v7.14).
    if bvid and not BV_RE.fullmatch(bvid):
        bvid = None
    if not bvid:
        match = BV_RE.search(parsed.path) or BV_RE.search(url)
        bvid = match.group(1) if match else None
    page = None
    raw_page = (query.get("p") or query.get("page") or [None])[0]
    if raw_page and str(raw_page).isdigit():
        page = int(raw_page)
    return bvid, page


def player_src(bvid: str, page: int | None = None) -> str:
    src = f"{PLAYER_BASE}?bvid={bvid}"
    if page and page > 1:
        src = f"{src}&page={page}"
    return src


def follow_b23(url: str) -> str:
    request = Request(url, headers={"User-Agent": _USER_AGENT})
    try:
        with urlopen(request, timeout=10) as response:
            return response.geturl() or url
    except (URLError, OSError, ValueError) as exc:
        raise EmbedNotFoundException(f"b23.tv lookup failed: {exc}") from exc


def remember_failed_lookup(url: str) -> None:
    """A lookup that found nothing is kept too, for FAILED_LOOKUP_TTL, so
    rendering the same line again does not ask the network again (v7.14).
    Wagtail's get_embed only caches what it found; the row it reads is the
    same one written here, keyed by the same hash."""
    from django.db import IntegrityError
    from wagtail.embeds.embeds import get_embed_hash
    from wagtail.embeds.models import Embed

    try:
        Embed.objects.update_or_create(
            hash=get_embed_hash(url),
            defaults={
                "url": url,
                "type": "video",
                "html": "",
                "cache_until": timezone.now() + FAILED_LOOKUP_TTL,
            },
        )
    except IntegrityError:
        pass  # another worker wrote the same row at the same moment


class BilibiliEmbedFinder(EmbedFinder):
    def accept(self, url):
        host = _hostname(url)
        if host in B23_HOSTS:
            return True
        if host in BILIBILI_HOSTS:
            return bool(extract_bvid_and_page(url)[0] or "/video/" in url)
        return False

    def find_embed(self, url, max_width=None, max_height=None):
        bvid, page = extract_bvid_and_page(url)
        if not bvid and _hostname(url) in B23_HOSTS:
            resolved = follow_b23(url)
            if _hostname(resolved) not in BILIBILI_HOSTS | B23_HOSTS:
                raise EmbedNotFoundException
            bvid, page = extract_bvid_and_page(resolved)
        if not bvid:
            raise EmbedNotFoundException
        src = player_src(bvid, page)
        html = (
            f'<iframe src="{src}" allowfullscreen="true" '
            'loading="lazy" referrerpolicy="strict-origin-when-cross-origin">'
            "</iframe>"
        )
        return {
            "title": bvid,
            "author_name": "bilibili",
            "provider_name": "Bilibili",
            "type": "video",
            "thumbnail_url": "",
            "width": max_width or 640,
            "height": max_height or 360,
            "html": html,
            # A failure row for this address may be sitting in the cache
            # with an hour's cache_until (remember_failed_lookup); without
            # this key update_or_create would keep it and the just-found
            # answer would look stale on the very next render.
            "cache_until": None,
        }
