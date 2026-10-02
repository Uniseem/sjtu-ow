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
    for spelling in ("\n    mask:", "\n    -webkit-mask:"):
        layers = rule[rule.index(spelling) :].split(";", 1)[0]
        assert 'url("../img/placeholders/horizon-far.svg")' in layers
        assert 'url("../img/placeholders/horizon-near.svg")' in layers
        assert layers.count("repeat-x") == 2
    # The page's own ground, even inside a night band.
    assert "background-color: var(--page-bg);" in rule
    root = _block(css, ":root {\n  color-scheme: light;")
    assert "--page-bg: var(--color-bg);" in root
    # The ridge is the edge, so no rule under it.
    edge = _block(css, ".c-pagehead--picture,\n  .c-stage:not(.c-stage--plain) {")
    assert "border-bottom: 0;" in edge


def _ridge(svg):
    """(fill-opacity, crest heights) of a horizon file's one polygon."""
    points, opacity = re.fullmatch(
        r'<svg [^>]+><polygon points="([^"]+)" fill="#000" '
        r'fill-opacity="([0-9.]+)"/></svg>\n',
        svg,
    ).groups()
    crest = points.split()[:-2]  # the last two close the shape at the bottom
    return float(opacity), [float(point.split(",")[1]) for point in crest]


def test_the_horizon_steps_down_in_two_flat_ridges():
    """The user, 10-03, of a misty first try: 「不要这种发光的，继续用那种折线，
    加一个过渡层就好了」. Two jagged ridges, each one flat tone: the far one a
    half-step, the near one the page. No gradient anywhere."""
    far, far_line = _ridge(placeholders.render_horizon_far())
    near, near_line = _ridge(placeholders.render_horizon_near())
    assert 0.3 <= far <= 0.7 and near == 1
    for line in (far_line, near_line):
        # Jagged: the crest turns up and down many times across.
        turns = sum(
            1
            for a, b, c in zip(line, line[1:], line[2:], strict=False)
            if (b - a) * (c - b) < 0
        )
        assert turns > 50


def test_the_horizon_drifts_without_a_seam():
    """「可以改成动态的」: each ridge ends where it began, so the tiles join,
    and the loop moves the far ridge one tile and the near one two (parallax)."""
    for svg in (placeholders.render_horizon_far(), placeholders.render_horizon_near()):
        _opacity, line = _ridge(svg)
        assert abs(line[0] - line[-1]) < 0.05
    css = INPUT_CSS.read_text(encoding="utf-8")
    rule = _block(
        css, ".c-pagehead--picture::before,\n  .c-stage:not(.c-stage--plain)::before {"
    )
    assert "animation: c-horizon 120s linear infinite;" in rule
    frames = _block(css, "@keyframes c-horizon {")
    assert re.search(r"\n\s+mask-position:\s+-1600px 100%,\s+-3200px 100%;", frames)


def test_the_light_neutrals_have_no_warm_cast():
    """The user tried the warm paper and said 「我不希望整体泛黄」: the light
    page, cards and text stay v5's neutral greys (blue at least equals red)."""
    css = INPUT_CSS.read_text(encoding="utf-8")
    light = dict(HEX.findall(css[: css.index("/* Dark values (13.2.2)")]))
    for name in ("bg", "surface", "surface-2", "line", "fg", "fg-2", "fg-3"):
        value = light[name]
        red, blue = int(value[1:3], 16), int(value[5:7], 16)
        assert blue >= red, (name, value)


def test_nothing_is_outlined_only_toned_apart():
    """「纯色切割，不特地去勾勒出边缘的」: no box or divider is drawn in the line
    colour. The two that stay: the rule in an article (content) and the edge
    of a white swatch on the style guide (or it would vanish)."""
    css = INPUT_CSS.read_text(encoding="utf-8")
    drawn = []
    selector = ""
    for line in css.splitlines():
        stripped = line.strip()
        if stripped.endswith("{") and not stripped.startswith("@"):
            selector = stripped[:-1].strip()
        if re.search(r"border[a-z-]*: 1px solid var\(--color-line\)", line):
            drawn.append(selector)
    assert sorted(drawn) == [".c-prose hr", ".c-swatch__chip"]


def test_a_list_is_a_group_of_tiles():
    css = INPUT_CSS.read_text(encoding="utf-8")
    group = _block(css, "\n  .c-rows {")
    assert "gap: 3px;" in group and "background" not in group
    # Anchored at the line start: the home page's two-column rule also says
    # `.c-rows > .c-row`, nested in a media query.
    tile = _block(css, "\n  .c-rows > .c-row {")
    assert "background-color: var(--color-surface);" in tile
    assert "border-radius: var(--radius-xs);" in tile
    first = _block(css, "\n  .c-rows > .c-row:first-child {")
    assert "border-top-left-radius: var(--radius-lg);" in first
    last = _block(css, "\n  .c-rows > .c-row:last-child {")
    assert "border-bottom-left-radius: var(--radius-lg);" in last
    # Table rows are cut apart by the page's ground, not ruled.
    assert "border-top: 2px solid var(--color-bg);" in _block(css, ".c-table td {")


def test_a_row_leads_with_its_date_as_type_not_a_box():
    """The user, 10-03, of the grey date square: 「感觉这个日期不是很符合站点风格」.
    The row is the tile; the date inside it is only type."""
    css = INPUT_CSS.read_text(encoding="utf-8")
    block = _block(css, "\n  .c-date {")
    assert "background" not in block and "border-radius" not in block
    day = _block(css, "\n  .c-date b {")
    assert "font-size: 2rem;" in day and "font-family: var(--font-figure);" in day


def test_section_titles_carry_the_peaks():
    css = INPUT_CSS.read_text(encoding="utf-8")
    rule = _block(css, ".c-sectionhead > h2::before {")
    # Both spellings: Safari still wants the prefix.
    assert '\n    mask: url("../img/placeholders/peaks.svg")' in rule
    assert '\n    -webkit-mask: url("../img/placeholders/peaks.svg")' in rule
    assert "background-color: var(--color-accent);" in rule
