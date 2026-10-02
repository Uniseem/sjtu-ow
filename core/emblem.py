"""The SJTU emblem in two layers for the homepage hero (design 13.2.5, v5.0):
the gear ring, which turns slowly, and everything else.

``manage.py render_emblem_layers`` writes them next to the emblem and the
files are committed; a test splits the emblem again and compares. The hero
colours them with CSS masks, so the shapes are all that matters here.
"""

from __future__ import annotations

import re
from pathlib import Path

from django.conf import settings

SOURCE = "img/sjtu-emblem.svg"
BODY = "img/sjtu-emblem-body.svg"
GEAR = "img/sjtu-emblem-gear.svg"

# Every path after <defs> is self-closing; the gear ring is by far the longest.
PATH = re.compile(r"<path\b[^>]*/>")


def static_file(name: str) -> Path:
    return Path(settings.BASE_DIR) / "static" / name


def layers(svg: str) -> tuple[str, str]:
    """(everything but the gear, the gear alone) from the emblem's source."""
    split = svg.index("</defs>")
    head, tail = svg[:split], svg[split:]
    gear = max(PATH.findall(tail), key=len)
    body = head + tail.replace(gear, "", 1)
    alone = head + PATH.sub(
        lambda match: match.group(0) if match.group(0) == gear else "", tail
    )
    return body, alone


def render() -> dict[str, str]:
    """The two layer files' contents, keyed by their static names."""
    source = static_file(SOURCE).read_text(encoding="utf-8").replace("\r\n", "\n")
    body, gear = layers(source)
    return {BODY: body, GEAR: gear}
