"""The pictures inside every letter (design 10.3, v7.4).

The site's look is flat silhouette drawing: under a picture head two jagged
ridges, the far one a half-tone, the near one the page itself. A letter's head
is SJTU red (``primary``) with the site mark on it and the same two ridges
along its bottom edge, the near one white so it runs into the card.

Mail clients do not show SVG (Gmail, Outlook, QQ Mail) and often hold back
pictures from elsewhere, so the shapes are drawn here with Pillow from the
site's own numbers and travel inside each message (``cid:``; ``core.mail``
attaches the ones a letter's HTML uses). ``render_email_art`` writes the
files; a test checks the committed ones match what this draws.
"""

from __future__ import annotations

import random
import re
from functools import cache
from pathlib import Path

from django.conf import settings
from django.templatetags.static import static
from PIL import Image, ImageDraw

from core import icons, placeholders

DIRECTORY = "img/email"
# Content-ID -> file under static/img/email. The layout points at cid:<key>.
ART = {"ow-mark": "mark.png", "ow-horizon": "horizon.png"}

PRIMARY = (155, 58, 51, 255)  # #9b3a33, the site's primary (13.2.2)
WHITE = (255, 255, 255, 255)
# The far ridge: half the card's white over the red, as the site's far ridge
# is half the page over the picture (placeholders.HORIZON_STEP).
FAR = (205, 157, 153, 255)  # halfway from PRIMARY to WHITE, #cd9d99

# Twice the size they are shown at (600 x 50, the site horizon's 12:1, and
# 36 x 36), for sharp screens.
WIDTH, HEIGHT = 1200, 100
MARK = 72
SUPERSAMPLE = 4


def mark() -> Image.Image:
    """The site icon the other way round: a white square, a red chevron."""
    return icons.draw(MARK, fill=WHITE, ink=PRIMARY)


def _ridge(seed: int, base: float, rough: float, size: tuple[int, int]):
    """The site's horizon line (placeholders._horizon) scaled to this strip."""
    width, height = size
    line = placeholders._tiling_ridge(
        random.Random(seed),
        placeholders.HORIZON_HEIGHT * base,
        placeholders.HORIZON_HEIGHT * rough,
    )
    sx = width / placeholders.WIDTH
    sy = height / placeholders.HORIZON_HEIGHT
    points = [(x * sx, y * sy) for x, y in line]
    return points + [(width, height), (0, height)]


def horizon() -> Image.Image:
    """Red above, the two ridges below; the bottom row is the card's white."""
    big = (WIDTH * SUPERSAMPLE, HEIGHT * SUPERSAMPLE)
    image = Image.new("RGBA", big, PRIMARY)
    pen = ImageDraw.Draw(image)
    # Same seeds and heights as the site's horizon-far / horizon-near.
    pen.polygon(_ridge(2026, 0.42, 0.26, big), fill=FAR)
    pen.polygon(_ridge(1896, 0.66, 0.18, big), fill=WHITE)
    return image.resize((WIDTH, HEIGHT), Image.Resampling.LANCZOS)


def files() -> dict[str, Image.Image]:
    return {"mark.png": mark(), "horizon.png": horizon()}


def folder() -> Path:
    return Path(settings.BASE_DIR) / "static" / DIRECTORY


def write(target: Path | None = None) -> list[Path]:
    target = target or folder()
    target.mkdir(parents=True, exist_ok=True)
    written = []
    for name, image in files().items():
        path = target / name
        image.save(path, format="PNG", optimize=True)
        written.append(path)
    return written


@cache
def _bytes(name: str) -> bytes:
    return (folder() / name).read_bytes()


CID = re.compile(r"cid:(ow-[a-z]+)")


def used(html: str) -> list[tuple[str, bytes]]:
    """(Content-ID, PNG) for each picture this HTML points at, once each."""
    seen = []
    for cid in CID.findall(html or ""):
        if cid in ART and cid not in seen:
            seen.append(cid)
    return [(cid, _bytes(ART[cid])) for cid in seen]


def for_browser(html: str) -> str:
    """The specimen page shows a letter in the browser, which cannot follow
    cid: links: point them at the same files under /static/."""
    return CID.sub(
        lambda match: (
            static(f"{DIRECTORY}/{ART[match.group(1)]}")
            if match.group(1) in ART
            else match.group(0)
        ),
        html,
    )
