"""Cover placeholders (design 13.2.5, round 090): an article or a tournament
without a cover shows one of the site's own abstract pictures, and always the
same one, so its card, its page and the prerendered copy agree."""

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


def test_the_committed_pictures_are_what_the_code_draws():
    """Change core/placeholders.py, then run render_placeholders and commit."""
    expected = sorted(placeholders.filename(i) for i in range(COUNT))
    assert sorted(p.name for p in FOLDER.glob("*.svg")) == expected
    for index in range(COUNT):
        name = placeholders.filename(index)
        assert _committed(name) == placeholders.render(index), name


def test_the_command_writes_every_picture_and_drops_stale_ones(tmp_path, settings):
    settings.BASE_DIR = tmp_path
    target = tmp_path / "static" / placeholders.DIRECTORY
    target.mkdir(parents=True)
    (target / "cover-99.svg").write_text("<svg/>", encoding="utf-8")
    (target / "keep.txt").write_text("not ours", encoding="utf-8")
    call_command("render_placeholders", stdout=open(tmp_path / "out.txt", "w"))
    names = sorted(p.name for p in target.glob("*.svg"))
    assert names == sorted(placeholders.filename(i) for i in range(COUNT))
    assert (target / "keep.txt").exists()
    for name in names:
        assert _committed(name, target) == _committed(name), name


def test_the_pictures_are_plain_graphics():
    """Same rules as the emblem (13.2.8): nothing that runs, nothing fetched,
    no words. Served from our origin, an SVG with a script would run there."""
    for index in range(COUNT):
        name = placeholders.filename(index)
        svg = _committed(name)
        assert svg.startswith(
            '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 1600 900" '
            'width="1600" height="900" preserveAspectRatio="xMidYMid slice">'
        ), name
        lowered = svg.lower()
        for bad in (
            "<script", "javascript:", "<foreignobject", "<image", "href=",
            "<text", "<style", "@import", " on",
        ):  # fmt: skip
            assert bad not in lowered, (name, bad)
        assert re.findall(r"url\((?!#)", svg) == [], name
        assert len(svg.encode("utf-8")) < 40_000, name


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
    assert 'width="640" height="360"' in plain_card
    covered_card = next(card for card in cards if ">有封面<" in card)
    assert placeholders.DIRECTORY not in covered_card
    assert "<img" in covered_card

    def figure(article):
        page = _main(client, article.url)
        start = page.index('<figure class="c-article__cover">')
        return page[start : page.index("</figure>", start)]

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
        assert placeholders.DIRECTORY not in html, path
        assert "tc" in html, path
