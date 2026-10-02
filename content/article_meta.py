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
    """(plain text, images, videos) of a StreamField body, without rendering
    it: rich text and quotes as text, image captions counted as text."""
    parts, images, videos = [], 0, 0
    for block in body or ():
        kind = block.block_type
        if kind == "paragraph":
            parts.append(strip_tags(getattr(block.value, "source", str(block.value))))
        elif kind == "quote":
            parts.extend(
                [block.value.get("text", ""), block.value.get("attribution", "")]
            )
        elif kind == "image":
            images += 1
            parts.append(block.value.get("caption", ""))
        elif kind == "video":
            videos += 1
    return "\n".join(part for part in parts if part), images, videos


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
