"""Light and dark (design 13.2.1 #5, v5.1): the system's mode by default, or
the visitor's pick in the masthead; everything follows it except the night
bands; the hero and the section heads have a scene for each mode."""

import re
from pathlib import Path

import pytest
from django.conf import settings
from django.templatetags.static import static

from content.tests.test_content import _image, _tree
from core import placeholders
from core.models import SiteSettings

ROOT = Path(settings.BASE_DIR)
INPUT_CSS = ROOT / "assets" / "css" / "input.css"
THEME_JS = ROOT / "static" / "js" / "theme.js"


def _css():
    return INPUT_CSS.read_text(encoding="utf-8")


def _rule(css, head):
    """The declarations of the first rule starting with ``head`` (one level)."""
    start = css.index(head)
    return css[start : css.index("\n  }", start)]


@pytest.fixture
def pages(db):
    _tree()


# --- the switch ------------------------------------------------------------------


def test_the_mode_is_set_before_the_page_paints(client, pages):
    """theme.js runs in <head>, blocking, ahead of the stylesheet, so a page
    never flashes in the other mode."""
    html = client.get("/").content.decode("utf-8")
    head = html[: html.index("</head>")]
    script = '<script src="/static/js/theme.js"></script>'
    assert script in head
    assert head.index(script) < head.index('rel="stylesheet"')


def test_the_masthead_offers_three_modes_once_the_script_runs(client, pages):
    """跟随系统, 浅色, 深色: in the bar from 640px, in the drawer on phones;
    both hidden until theme.js shows them (without it the system decides)."""
    html = client.get("/").content.decode("utf-8")
    masthead = html[html.index('<header class="c-masthead">') : html.index("</header>")]
    menus = re.findall(
        r"<(details|div) class=\"([^\"]*)\" data-theme-menu hidden>", masthead
    )
    assert menus == [("details", "c-theme max-sm:hidden"), ("div", "sm:hidden")]
    starts = [m.start() for m in re.finditer("data-theme-menu", masthead)]
    for start, end in zip(starts, [*starts[1:], len(masthead)], strict=True):
        menu = masthead[start:end]
        choices = re.findall(r'data-theme-choice="(\w+)" aria-pressed="false">', menu)
        assert choices == ["system", "light", "dark"]
        for label in ("跟随系统", "浅色", "深色"):
            assert label in menu


def test_the_script_keeps_a_pick_and_forgets_it_for_the_system():
    js = THEME_JS.read_text(encoding="utf-8")
    assert 'var KEY = "ow-theme";' in js
    assert 'root.setAttribute("data-theme", choice);' in js
    assert 'root.removeAttribute("data-theme");' in js
    assert "window.localStorage.setItem(KEY, choice);" in js
    assert "window.localStorage.removeItem(KEY);" in js
    # Only light and dark are written; anything else means the system.
    assert 'choice === "light" || choice === "dark"' in js
    # Private mode throws on storage: the page still works.
    assert js.count("try {") == 2


# --- what follows the mode -------------------------------------------------------


def test_only_the_footer_and_banners_with_a_cover_stay_night():
    """v5.0 made the masthead, heads, hero and figures night in both modes;
    in light mode the homepage read as a dark-mode page (v5.1)."""
    css = _css()
    head = css.index("  /* ---- Night bands (v5.1)")
    selectors = css[css.index("\n  .", head) : css.index("{", head)].split(",")
    assert [s.strip() for s in selectors] == [
        ".c-stage:not(.c-stage--plain)",
        ".c-footer",
    ]
    for head in (
        "\n  .c-masthead {",
        "\n  .c-pagehead {",
        "\n  .c-hero {",
        "\n  .c-stats {",
        "\n  .c-stage {",
    ):
        rule = _rule(css, head)
        assert "night" not in rule, head
    assert "background-color: var(--color-surface);" in _rule(css, "\n  .c-masthead {")


@pytest.mark.parametrize("veil", [".c-hero::after {", ".c-pagehead--picture::after {"])
def test_the_hero_and_section_heads_are_veiled_in_the_page_ground(veil):
    """White on a light page, near black on a dark one (13.2.5 图上的字)."""
    css = _css()
    blocks = [m.start() for m in re.finditer(re.escape(veil), css)]
    assert blocks
    for start in blocks:
        rule = css[start : css.index("}", start)]
        assert "var(--color-bg)" in rule
        assert "--color-night" not in rule and "--color-black" not in rule


def test_each_scene_shows_only_in_its_own_mode():
    css = _css()
    light = _rule(css, "\n  .c-scene--light {")
    dark = css[css.index("\n  .c-scene--dark {") :]
    dark = dark[: dark.index("\n  }\n")]
    assert "@variant dark {\n      display: none;" in light
    assert dark.startswith("\n  .c-scene--dark {\n    display: none;")
    assert "@variant dark {\n      display: block;" in dark


# --- the pictures ----------------------------------------------------------------


@pytest.mark.parametrize(
    "path,section",
    [("/news/", "news"), ("/tournaments/", "tournaments"), ("/scrims/", "scrims"),
     ("/teams/", "teams"), ("/members/", "members")],
)  # fmt: skip
def test_a_section_head_has_its_scene_by_day_and_night(client, pages, path, section):
    html = client.get(path).content.decode("utf-8")
    head = html[html.index('<header class="c-pagehead c-pagehead--picture">') :]
    head = head[: head.index("</header>")]
    paths = placeholders.section_paths(section)
    for mode in ("light", "dark"):
        assert (
            f'<img class="c-pagehead__img c-scene c-scene--{mode}" '
            f'src="{static(paths[mode])}" alt="" width="2400" height="640">'
        ) in head


def test_an_uploaded_banner_is_used_in_both_modes(client, pages):
    site = SiteSettings.load()
    site.banner_teams = _image("队伍横幅")
    site.save()
    html = client.get("/teams/").content.decode("utf-8")
    head = html[html.index('<header class="c-pagehead c-pagehead--picture">') :]
    head = head[: head.index("</header>")]
    assert "c-scene" not in head and placeholders.DIRECTORY not in head
    assert re.search(r'<img class="c-pagehead__img" src="/media/[^"]+" alt=""', head)


# --- the emblem on the hero (13.2.5) --------------------------------------------


def test_the_emblem_layers_are_what_the_splitter_draws():
    """Change the emblem, then run render_emblem_layers and commit."""
    from core import emblem

    for name, content in emblem.render().items():
        committed = emblem.static_file(name).read_text(encoding="utf-8")
        assert committed.replace("\r\n", "\n") == content, name


def test_the_gear_is_the_emblem_s_longest_path_and_alone_in_its_layer():
    from core import emblem

    source = emblem.static_file(emblem.SOURCE).read_text(encoding="utf-8")
    body, gear = emblem.layers(source.replace("\r\n", "\n"))
    tail = source[source.index("</defs>") :]
    paths = emblem.PATH.findall(tail)
    longest = max(paths, key=len)
    assert emblem.PATH.findall(gear[gear.index("</defs>") :]) == [longest]
    assert longest not in body
    assert len(emblem.PATH.findall(body[body.index("</defs>") :])) == len(paths) - 1


def test_the_emblem_is_see_through_in_the_mode_s_colours_and_its_gear_turns():
    """v5.1: larger and see-through, so it sits in the picture; ink and red
    follow the mode; the gear turns once in 90 s (stopped by the reduced-motion
    rule in the base layer)."""
    css = _css()
    body = _rule(css, "\n  .c-hero__emblem > span {")
    gear = _rule(css, "\n  .c-hero__emblem > .c-hero__emblem-gear {")
    assert 'mask: url("../img/sjtu-emblem-body.svg")' in body
    assert "color-mix(in oklab, var(--color-fg) 20%, transparent)" in body
    assert 'mask-image: url("../img/sjtu-emblem-gear.svg")' in gear
    assert "color-mix(in oklab, var(--color-primary) 55%, transparent)" in gear
    assert "animation: c-hero-gear 90s linear infinite;" in gear
    wide = css[css.index("@media (min-width: 1024px) {\n    .c-hero__emblem {") :]
    assert "width: min(40rem, 46vw, calc(100svh - 16rem));" in wide[:200]
