"""Bilibili-only embed finder (design 5.2)."""

from __future__ import annotations

import re
from urllib.error import URLError
from urllib.parse import parse_qs, urlparse
from urllib.request import Request, urlopen

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


def _hostname(url: str) -> str:
    return (urlparse(url).hostname or "").lower()


def extract_bvid_and_page(url: str) -> tuple[str | None, int | None]:
    parsed = urlparse(url)
    query = parse_qs(parsed.query)
    bvid = (query.get("bvid") or [None])[0]
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
        }
