"""The site icon in the sizes browsers and phones ask for (design 13.2.5, v6.55).

static/img/favicon.svg is the original. Pillow cannot read SVG, so this draws
the same shape (SJTU red square, a white chevron) from its numbers, eight
times larger and then scaled down for smooth edges. ``render_icons`` writes
the files; a test checks the committed ones match what this draws.
"""

from __future__ import annotations

from io import BytesIO
from pathlib import Path

from PIL import Image, ImageDraw

RED = (164, 22, 26, 255)  # #a4161a, as in favicon.svg
WHITE = (255, 255, 255, 255)
BOX, CORNER = 32, 9  # favicon.svg: viewBox 32, rx 9
CHEVRON = [(8, 21.5), (16, 13.5), (24, 21.5)]
STROKE = 3.2
SUPERSAMPLE = 8
ICO_SIZES = (16, 32, 48)
# (file under static/img, size, rounded corners)
PNGS = (
    ("apple-touch-icon.png", 180, False),  # iOS rounds the corners itself
    ("icon-192.png", 192, True),
    ("icon-512.png", 512, True),
)


def draw(size: int, *, rounded: bool = True) -> Image.Image:
    big = size * SUPERSAMPLE
    scale = big / BOX
    image = Image.new("RGBA", (big, big), (0, 0, 0, 0))
    pen = ImageDraw.Draw(image)
    if rounded:
        pen.rounded_rectangle(
            (0, 0, big - 1, big - 1), radius=round(CORNER * scale), fill=RED
        )
    else:
        pen.rectangle((0, 0, big - 1, big - 1), fill=RED)
    points = [(x * scale, y * scale) for x, y in CHEVRON]
    width = round(STROKE * scale)
    pen.line(points, fill=WHITE, width=width, joint="curve")
    for x, y in (points[0], points[-1]):  # round ends, as stroke-linecap
        pen.ellipse(
            (x - width / 2, y - width / 2, x + width / 2, y + width / 2), fill=WHITE
        )
    return image.resize((size, size), Image.Resampling.LANCZOS)


def ico_bytes() -> bytes:
    out = BytesIO()
    draw(max(ICO_SIZES)).save(
        out, format="ICO", sizes=[(size, size) for size in ICO_SIZES]
    )
    return out.getvalue()


def files() -> dict[str, Image.Image | bytes]:
    """What goes under static/img: name -> image (PNG) or bytes (ICO)."""
    made: dict[str, Image.Image | bytes] = {"favicon.ico": ico_bytes()}
    for name, size, rounded in PNGS:
        made[name] = draw(size, rounded=rounded)
    return made


def write(folder: Path) -> list[Path]:
    written = []
    for name, made in files().items():
        target = folder / name
        if isinstance(made, bytes):
            target.write_bytes(made)
        else:
            made.save(target, format="PNG", optimize=True)
        written.append(target)
    return written
