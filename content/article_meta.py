"""What an article's head says about it, and its table of contents
(design-details 6.2, 6.3, 6.5; v5.2)."""

from __future__ import annotations

import math
import re
from dataclasses import dataclass

from django.utils.html import strip_tags
from django.utils.safestring import mark_safe

CJK = re.compile(r"[㐀-䶿一-鿿豈-﫿]")
LATIN_WORD = re.compile(r"[A-Za-z0-9]+(?:['’.-][A-Za-z0-9]+)*")
HEADING = re.compile(r"<(h[23])(\s[^>]*)?>(.*?)</\1\s*>", re.S | re.I)
ID_ATTR = re.compile(r"\sid=(\"[^\"]*\"|'[^']*'|\S+)", re.I)
CHARS_PER_MINUTE = 400
SECONDS_PER_IMAGE = 10
SECONDS_PER_VIDEO = 60
TOC_MIN_HEADINGS = 3


def body_text(body) -> tuple[str, int, int]:
    """(plain text, images, videos) of a Markdown body (v6.70): what the
    reader sees, so no asterisks or link addresses; image captions count."""
    from content.markdown import analyse, plain_html

    rendered = analyse(body)
    return plain_html(rendered.html), rendered.images, rendered.videos


def stored_counts(body) -> tuple[str, int, int]:
    """(plain text, words, reading minutes) kept on the row at save time
    (v7.14), so pages, cards and search never re-parse the body."""
    text, images, videos = body_text(body)
    words = word_count(text)
    return text, words, reading_minutes(words, images, videos)


def word_count(text: str) -> int:
    """Chinese characters plus Latin words; no punctuation or spaces (6.3)."""
    return len(CJK.findall(text)) + len(LATIN_WORD.findall(text))


def reading_minutes(words: int, images: int = 0, videos: int = 0) -> int:
    seconds = (
        words / CHARS_PER_MINUTE * 60
        + images * SECONDS_PER_IMAGE
        + videos * SECONDS_PER_VIDEO
    )
    return max(1, math.ceil(seconds / 60))


@dataclass(frozen=True)
class Heading:
    level: int  # 2 or 3
    anchor: str
    text: str


def anchor_headings(html: str) -> tuple[str, list[Heading]]:
    """Give every h2 and h3 an id (h-1, h-2, …; numbers rather than the
    words, so no Chinese anchors and no clashes) and list them (6.5)."""
    headings: list[Heading] = []

    def replace(match):
        tag, attrs, inner = match.group(1).lower(), match.group(2) or "", match.group(3)
        anchor = f"h-{len(headings) + 1}"
        headings.append(
            Heading(int(tag[1]), anchor, " ".join(strip_tags(inner).split()))
        )
        attrs = ID_ATTR.sub("", attrs)
        return f'<{tag} id="{anchor}"{attrs}>{inner}</{tag}>'

    return mark_safe(HEADING.sub(replace, html)), headings


@dataclass
class ArticleFacts:
    words: int
    minutes: int
    images: int
    videos: int


def facts(body) -> ArticleFacts:
    text, images, videos = body_text(body)
    words = word_count(text)
    return ArticleFacts(words, reading_minutes(words, images, videos), images, videos)
