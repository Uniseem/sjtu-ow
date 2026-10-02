"""Cover placeholders (design 13.2.5, round 090): an article or a tournament
without a cover shows one of the site's own abstract pictures, and always the
same one, so its card, its page and the prerendered copy agree. Since v5.1 the
pictures move, and the hero and the section heads have a daylight version."""

import re
from datetime import timedelta
from itertools import pairwise
from pathlib import Path

import pytest
from django.conf import settings
from django.core.management import call_command
from django.templatetags.static import static

from content.models import ArticleCategory, ArticlePage
from content.tests.test_content import _article, _image, _tree, _user
from core import placeholders
from tournaments.models import Tournament
from tournaments.tests.test_public_pages import _tournament

FOLDER = Path(settings.BASE_DIR) / "static" / placeholders.DIRECTORY
COUNT = len(placeholders.CATALOGUE)
DAY = timedelta(days=1)


def _committed(name, folder=FOLDER):
    # Git may check text files out with CRLF on Windows (core.autocrlf).
    return (folder / name).read_text(encoding="utf-8").replace("\r\n", "\n")


def _main(client, path):
    response = client.get(path)
    assert response.status_code == 200, path
    html = response.content.decode("utf-8")
    return html[html.index("<main") : html.index("</main>")]


def _src(obj):
    return f'src="{static(placeholders.static_path(obj))}"'


# --- the files -----------------------------------------------------------------


FILES = placeholders.every_file()
MOVING = placeholders.moving_files()
STILL_FILES = placeholders.still_files()


def test_the_committed_pictures_are_what_the_code_draws():
    """Change core/placeholders.py, then run render_placeholders and commit."""
    assert len(MOVING) == COUNT + len(placeholders.SECTION_SCENES) == 42
    # v5.2: the five base pictures and the footer ridge (design-details 1.9);
    # v6.0 draft: the horizon and the peaks, both masks.
    assert sorted(STILL_FILES) == [
        "horizon.svg",
        *(f"hue-{n}.svg" for n in range(1, 6)),
        "peaks.svg",
        "ridge.svg",
    ]
    assert FILES == {**MOVING, **STILL_FILES}
    assert sorted(p.name for p in FOLDER.glob("*.svg")) == sorted(FILES)
    for name, svg in FILES.items():
        assert _committed(name) == svg, name


def test_the_command_writes_every_picture_and_drops_stale_ones(tmp_path, settings):
    settings.BASE_DIR = tmp_path
    target = tmp_path / "static" / placeholders.DIRECTORY
    target.mkdir(parents=True)
    (target / "cover-99.svg").write_text("<svg/>", encoding="utf-8")
    (target / "section-gone-light.svg").write_text("<svg/>", encoding="utf-8")
    (target / "keep.txt").write_text("not ours", encoding="utf-8")
    call_command("render_placeholders", stdout=open(tmp_path / "out.txt", "w"))
    names = sorted(p.name for p in target.glob("*.svg"))
    assert names == sorted(FILES)
    assert (target / "keep.txt").exists()
    for name in names:
        assert _committed(name, target) == _committed(name), name


# Drawn to a page's width or as a mark, not as a 16:9 scene.
EDGES = (placeholders.RIDGE_FILE, placeholders.HORIZON_FILE, placeholders.PEAKS_FILE)


def test_the_pictures_are_plain_graphics():
    """Same rules as the emblem (13.2.8): nothing that runs, nothing fetched,
    no words. Served from our origin, an SVG with a script would run there.
    The one <style> holds the motion and nothing else (v5.1); the still
    pictures have none (v5.2)."""
    for name, svg in FILES.items():
        if name not in EDGES:
            assert svg.startswith(
                '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 1600 900" '
                'width="1600" height="900" preserveAspectRatio="xMidYMid slice">'
            ), name
        lowered = svg.lower()
        for bad in (
            "<script", "javascript:", "<foreignobject", "<image", "href=",
            "<text", "@import", " on", "expression(", "behavior:",
        ):  # fmt: skip
            assert bad not in lowered, (name, bad)
        assert re.findall(r"url\((?!#)", svg) == [], name
        assert len(svg.encode("utf-8")) < 40_000, name
        if name in STILL_FILES:
            assert "<style" not in lowered and "class=" not in lowered, name
            continue
        assert lowered.count("<style") == 1, name
        style = svg[svg.index("<style>") + 7 : svg.index("</style>")]
        # Only class rules (.m12{…}), the keyframes they name and the still rule.
        rest = re.sub(r"\.m\d+\{[^{}]*\}", "", style)
        rest = re.sub(r"@keyframes [a-z]+\{(?:[^{}]*\{[^{}]*\})+\}", "", rest)
        assert rest == placeholders.STILL, name


def test_every_picture_moves_and_stands_still_under_reduced_motion():
    """v5.1: 「现在的这些图片都变成动图」, and 「减少动态效果」 stops them
    (13.2.4)."""
    assert placeholders.STILL == (
        "@media (prefers-reduced-motion:reduce){*{animation:none!important}}"
    )
    for name, svg in MOVING.items():
        named = set(re.findall(r"animation:([a-z]+) ", svg))
        assert named, name
        assert named <= set(placeholders.KEYFRAMES), name
        for frames in named:
            assert f"@keyframes {frames}{{" in svg, (name, frames)
        # Every rule is used by something drawn.
        for cid in re.findall(r"\.(m\d+)\{", svg):
            assert f'class="{cid}"' in svg, (name, cid)
        assert svg.count(placeholders.STILL) == 1, name


def _shapes(svg):
    """Where things are, without their colours: every sub-path, polygon and
    circle."""
    found = set()
    for d in re.findall(r' d="([^"]+)"', svg):
        found.update("M" + part for part in d.split("M") if part)
    found.update(re.findall(r' points="([^"]+)"', svg))
    found.update(re.findall(r'<circle cx="([^"]+)" cy="([^"]+)" r="([^"]+)"', svg))
    return found


@pytest.mark.parametrize("section", sorted(placeholders.SECTION_SCENES))
def test_a_place_by_day_is_the_same_scene_as_at_night(section):
    """v5.1: the light mode's version keeps every tower, ridge and shape of
    the night one; only the colours change (and clouds pass)."""
    paths = placeholders.section_paths(section)
    night = _committed(Path(paths["dark"]).name)
    day = _committed(Path(paths["light"]).name)
    assert night != day
    assert _shapes(day) == _shapes(night)


def test_there_are_nine_scenes_and_neighbours_never_share_one():
    styles = [style for style, _variant in placeholders.CATALOGUE]
    assert COUNT == 36
    assert len(set(styles)) == 9
    assert set(placeholders.STYLE_LABELS) == set(styles)
    assert all(a != b for a, b in pairwise(styles))
    assert len({placeholders.render(i) for i in range(COUNT)}) == COUNT


@pytest.mark.django_db  # a Wagtail page looks up its default locale
def test_each_object_keeps_its_picture_and_neighbours_get_different_scenes():
    first = placeholders.pick(Tournament(pk=7))
    assert placeholders.pick(Tournament(pk=7)) == first
    for model in (Tournament, ArticlePage):
        picks = [placeholders.pick(model(pk=pk)) for pk in range(1, 12)]
        scenes = [placeholders.CATALOGUE[i][0] for i in picks]
        assert all(a != b for a, b in pairwise(scenes)), model
    # An article and a tournament with the same id do not share a picture.
    assert all(
        placeholders.pick(Tournament(pk=pk)) != placeholders.pick(ArticlePage(pk=pk))
        for pk in range(1, 40)
    )
    # A page previewed before its first save has no id yet.
    assert 0 <= placeholders.pick(ArticlePage()) < COUNT


def test_no_template_falls_back_to_a_grey_block():
    root = Path(settings.BASE_DIR)
    css = (root / "assets" / "css" / "input.css").read_text(encoding="utf-8")
    assert "c-media__none" not in css
    for path in root.glob("**/templates/**/*.html"):
        if ".venv" in path.parts:
            continue
        assert "c-media__none" not in path.read_text(encoding="utf-8"), path


# --- the pages -----------------------------------------------------------------


@pytest.fixture
def site(db):
    home, news = _tree()
    return news, _user(nickname="写稿的"), ArticleCategory.objects.get(slug="guide")


def test_an_article_without_a_cover_shows_its_picture_on_card_and_page(client, site):
    news, author, guide = site
    plain = _article(news, guide, author, title="没封面", slug="plain")
    covered = _article(news, guide, author, title="有封面", slug="cv", cover=_image())
    listing = _main(client, "/news/")
    cards = listing.split('<article class="c-media">')[1:]
    plain_card = next(card for card in cards if ">没封面<" in card)
    assert _src(plain) in plain_card
    assert 'width="960" height="540"' in plain_card
    covered_card = next(card for card in cards if ">有封面<" in card)
    assert placeholders.DIRECTORY not in covered_card
    assert "<img" in covered_card

    def figure(article):
        # The cover across the head of the page (design-details 6.2).
        page = _main(client, article.url)
        start = page.index('<header class="c-cover">')
        return page[start : page.index('<div class="c-cover__body">', start)]

    assert _src(plain) in figure(plain)
    assert placeholders.DIRECTORY not in figure(covered)
    assert "<img" in figure(covered)

    home = _main(client, "/")
    assert _src(plain) in home


def test_a_tournament_without_a_cover_shows_its_picture_on_card_banner_and_home(
    client, db
):
    _tree()
    plain = _tournament("没封面的赛事", opens=-DAY, closes=DAY)
    listing = _main(client, "/tournaments/")
    card = listing[listing.index("data-tournament-card") :]
    assert _src(plain) in card[: card.index("</article>")]

    detail = _main(client, plain.get_absolute_url())
    banner = detail[detail.index("<header") : detail.index("</header>")]
    # The banner is the picture one, with the scrim, not the plain band.
    assert banner.startswith('<header class="c-stage">')
    assert re.search(
        r'<img src="[^"]+" width="2400" height="900" class="c-stage__img"', banner
    )
    assert _src(plain) in banner

    home = _main(client, "/")
    feature = home[home.index('data-next-up="tournament"') :]
    assert _src(plain) in feature[: feature.index("</article>")]
    assert 'class="c-feature__img"' in feature[: feature.index("</article>")]


def test_a_tournament_with_a_cover_keeps_it(client, db):
    _tree()
    covered = _tournament("有封面的赛事", opens=-DAY, closes=DAY)
    covered.cover = _image("tc")
    covered.save()
    for path in ("/tournaments/", covered.get_absolute_url(), "/"):
        html = _main(client, path)
        # The hero and the section head have their own scenes (v5.0).
        html = re.sub(r'<img class="c-(?:hero|pagehead)__img[^>]*>', "", html)
        assert placeholders.DIRECTORY not in html, path
        assert "tc" in html, path


# --- the base pictures and the footer ridge (design-details 1.5, 1.9, 2.2) -----


def test_the_five_base_pictures_are_still_landscapes_in_the_label_order():
    """Faces and team logos without a picture stand on one of five still
    landscapes; a page can hold dozens, so they do not move (1.9)."""
    assert sorted(placeholders.HUE_SCENES) == [1, 2, 3, 4, 5]
    styles = [placeholders.HUE_SCENES[n][0] for n in range(1, 6)]
    assert len(set(styles)) == 5
    for n in range(1, 6):
        svg = STILL_FILES[f"hue-{n}.svg"]
        assert "animation" not in svg and "<style" not in svg
        assert svg == placeholders.render_hue(n)


def test_the_stylesheet_puts_each_base_picture_on_its_class():
    css = (Path(settings.BASE_DIR) / "assets" / "css" / "input.css").read_text(
        encoding="utf-8"
    )
    tints = ["primary-soft", "accent-soft", "info-soft", "ok-soft", "warn-soft"]
    for n, tint in enumerate(tints, start=1):
        rule = css[css.index(f"\n  .c-hue-{n} {{") :]
        rule = rule[: rule.index("}")]
        assert f'url("../img/placeholders/hue-{n}.svg")' in rule
        assert f"var(--color-{tint})" in rule  # while it loads


def test_the_footer_ridge_is_drawn_in_the_night_colours():
    """The front ridge has to be the footer's own ground or a seam shows."""
    import re as _re

    css = (Path(settings.BASE_DIR) / "assets" / "css" / "input.css").read_text(
        encoding="utf-8"
    )
    tokens = dict(_re.findall(r"--color-([a-z0-9-]+):\s*(#[0-9a-f]{6})", css))
    assert placeholders.RIDGE_SHADES == (
        tokens["night-2"],
        tokens["night-surface"],
        tokens["night"],
    )
    ridge = STILL_FILES[placeholders.RIDGE_FILE]
    assert ridge.startswith(
        '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 1600 160"'
    )
    assert 'preserveAspectRatio="none"' in ridge
    assert [f'fill="{shade}"' in ridge for shade in placeholders.RIDGE_SHADES] == [
        True,
        True,
        True,
    ]
    footer = css[css.index("\n  .c-footer::before {") :]
    assert 'url("../img/placeholders/ridge.svg")' in footer[: footer.index("}")]
