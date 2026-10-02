"""Branch claude/flat-muted-ui (v6.0 draft): the placeholder art's flat,
layered, muted look carried into the interface.

The user, 2026-10-03: 「把现在这个 svg 的扁平风格……以及它的这种比较克制比较淡的色调
风格去应用到整个站点（就是ui那些东西）」. The palette is drawn from the art; the
picture heads sink into the page under a horizon; section titles carry a small
pair of peaks.
"""

import re
from pathlib import Path

from django.conf import settings

from core import placeholders

INPUT_CSS = Path(settings.BASE_DIR) / "assets" / "css" / "input.css"
HEX = re.compile(r"--color-([a-z0-9-]+):\s*(#[0-9a-fA-F]{6})")
# Restrained: nothing in the interface's palette or the base pictures is more
# colourful than this. Chroma (the spread between the strongest and weakest
# channel), not HSL saturation, which calls a pale cream loud. The old
# Overwatch orange was 0.88, the old SJTU red 0.56.
MOST_COLOURFUL = 0.5


def _chroma(value):
    channels = [int(value[i : i + 2], 16) / 255 for i in (1, 3, 5)]
    return max(channels) - min(channels)


def _block(css, opening):
    start = css.index(opening)
    depth = 0
    for index in range(start, len(css)):
        if css[index] == "{":
            depth += 1
        elif css[index] == "}":
            depth -= 1
            if depth == 0:
                return css[start:index]
    raise AssertionError(opening)


def test_every_colour_token_is_restrained():
    css = INPUT_CSS.read_text(encoding="utf-8")
    loud = [
        f"{name} {value} {_chroma(value):.2f}"
        for name, value in HEX.findall(css)
        if name not in ("white", "black") and _chroma(value) > MOST_COLOURFUL
    ]
    assert loud == []


def test_the_base_pictures_are_muted_too():
    loud = []
    for hue, (_style, _variant, palette) in placeholders.HUE_SCENES.items():
        for key, value in palette.items():
            for colour in value if isinstance(value, list) else [value]:
                if _chroma(colour) > MOST_COLOURFUL:
                    loud.append(f"hue-{hue} {key} {colour}")
    assert loud == []


def test_picture_heads_sink_into_the_page_under_a_horizon():
    css = INPUT_CSS.read_text(encoding="utf-8")
    horizon = ".c-pagehead--picture::before,\n  .c-stage:not(.c-stage--plain)::before {"
    rule = _block(css, horizon)
    assert '\n    mask: url("../img/placeholders/horizon.svg")' in rule
    assert '\n    -webkit-mask: url("../img/placeholders/horizon.svg")' in rule
    # The page's own ground, even inside a night band.
    assert "background-color: var(--page-bg);" in rule
    root = _block(css, ":root {\n  color-scheme: light;")
    assert "--page-bg: var(--color-bg);" in root
    # The ridge is the edge, so no rule under it.
    edge = _block(css, ".c-pagehead--picture,\n  .c-stage:not(.c-stage--plain) {")
    assert "border-bottom: 0;" in edge


def test_the_horizon_fades_its_far_ridge_like_the_art():
    svg = placeholders.render_horizon()
    far, near = re.findall(r'<polygon points="[^"]+" fill="([^"]+)"/>', svg)
    assert far == "url(#mist)" and near == "#000"
    assert 'stop-opacity="0"' in svg  # clear at the crest


def test_section_titles_carry_the_peaks():
    css = INPUT_CSS.read_text(encoding="utf-8")
    rule = _block(css, ".c-sectionhead > h2::before {")
    # Both spellings: Safari still wants the prefix.
    assert '\n    mask: url("../img/placeholders/peaks.svg")' in rule
    assert '\n    -webkit-mask: url("../img/placeholders/peaks.svg")' in rule
    assert "background-color: var(--color-accent);" in rule
