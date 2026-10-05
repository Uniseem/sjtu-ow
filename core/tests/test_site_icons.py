"""Round 171: the site icon in every size asked for (design 13.2.5, v6.55)."""

import json
from io import BytesIO
from pathlib import Path

import pytest
from django.core.management import call_command
from PIL import Image

from core import icons

IMG = Path(__file__).resolve().parents[2] / "static" / "img"


def _close(pixel, colour, slack=12):
    return all(abs(a - b) <= slack for a, b in zip(pixel, colour, strict=False))


def _at(image, x, y):
    """A point given in favicon.svg's 32-unit box."""
    scale = image.width / icons.BOX
    return image.getpixel((round(x * scale), round(y * scale)))


@pytest.mark.parametrize(("name", "size", "rounded"), icons.PNGS)
def test_each_png_is_the_svg_shape(name, size, rounded):
    image = Image.open(IMG / name).convert("RGBA")
    assert image.size == (size, size)
    assert _close(_at(image, 4, 16), icons.RED)  # the square
    assert _close(_at(image, 16, 13.5), icons.WHITE)  # the chevron's tip
    assert _close(_at(image, 16, 24), icons.RED)  # under the chevron
    corner = image.getpixel((0, 0))
    if rounded:
        assert corner[3] == 0  # see-through outside the rounded corner
    else:
        assert _close(corner, icons.RED)  # iOS rounds it


def test_the_ico_has_three_sizes():
    ico = Image.open(IMG / "favicon.ico")
    assert ico.info["sizes"] == {(16, 16), (32, 32), (48, 48)}
    ico.size = (48, 48)
    assert _close(_at(ico.convert("RGBA"), 16, 13.5), icons.WHITE, slack=40)


def test_the_committed_files_are_what_the_code_draws():
    """After changing core/icons.py, run render_icons and commit."""
    for name, size, rounded in icons.PNGS:
        committed = Image.open(IMG / name).convert("RGBA")
        assert committed.tobytes() == icons.draw(size, rounded=rounded).tobytes(), name
    drawn = Image.open(BytesIO(icons.ico_bytes()))
    committed = Image.open(IMG / "favicon.ico")
    assert drawn.info["sizes"] == committed.info["sizes"]
    for size in icons.ICO_SIZES:
        drawn.size = committed.size = (size, size)
        assert drawn.convert("RGBA").tobytes() == committed.convert("RGBA").tobytes()


def test_the_manifest_names_files_that_exist():
    manifest = json.loads((IMG.parent / "manifest.webmanifest").read_text("utf-8"))
    assert manifest["short_name"] == "SJTU-OW"
    for icon in manifest["icons"]:
        assert (IMG.parent / icon["src"]).exists()
        width, height = Image.open(IMG.parent / icon["src"]).size
        assert icon["sizes"] == f"{width}x{height}"


@pytest.mark.django_db
def test_pages_point_at_them_and_the_root_addresses_lead_there(client):
    call_command("init_site", verbosity=0)
    html = client.get("/").content.decode()
    for needle in (
        'rel="icon" href="/static/img/favicon.ico',
        'rel="icon" href="/static/img/favicon.svg',
        'rel="apple-touch-icon" href="/static/img/apple-touch-icon.png',
        'rel="manifest" href="/static/manifest.webmanifest',
    ):
        assert needle in html
    for path in ("/favicon.ico", "/apple-touch-icon.png"):
        response = client.get(path)
        assert response.status_code == 301
        assert response["Location"].startswith("/static/img/" + path[1:].split(".")[0])
