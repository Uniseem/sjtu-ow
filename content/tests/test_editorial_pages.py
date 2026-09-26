"""The 刊物 pages on v3.0 (design 13.2.8, round 083): the news list as cards,
the article page's meta line, byline and related card, search, and pages
without the v2.0 Latin eyebrows."""

import re

import pytest

from content.models import ArticleCategory
from content.tests.test_content import _article, _image, _tree, _user
from core.tests.test_design_system import INPUT_CSS, _block


def _main(response):
    html = response.content.decode("utf-8")
    return html[html.index("<main") : html.index("</main>")]


@pytest.fixture
def site(db):
    home, news = _tree()
    return news, _user(nickname="写稿的"), ArticleCategory.objects.get(slug="guide")


def test_the_news_list_is_a_grid_of_cards(client, site):
    news, author, guide = site
    _article(news, guide, author, title="有封面", slug="c", cover=_image("c"))
    _article(news, guide, author, title="没封面", slug="p")
    notice = ArticleCategory.objects.get(slug="notice")
    _article(news, notice, author, title="公告没封面", slug="n")
    html = _main(client.get("/news/"))
    grid = html[html.index('<ol class="c-posts"') : html.index("</ol>")]
    assert grid.count('<li class="c-post">') == 3
    cards = grid.split('<li class="c-post">')[1:]
    covered = next(card for card in cards if ">有封面<" in card)
    assert "<img" in covered and "c-hatch" not in covered
    plain = next(card for card in cards if ">没封面<" in card)
    # No cover: the category's wash with its icon, not an empty box.
    assert 'class="c-hatch c-hatch--guide"' in plain
    assert 'class="c-hatch__icon"' in plain
    # Each category has its own tones and icon, the default (公告) included.
    other = next(card for card in cards if ">公告没封面<" in card)
    assert 'class="c-hatch c-hatch--notice"' in other
    assert 'class="c-hatch__icon"' in other

    def icon(card):
        return re.search(
            r'class="c-hatch__icon"[^>]*>\s*(<path d="[^"]+")', card
        ).group(1)

    assert icon(plain) != icon(other)
    assert (
        '<span class="c-avatar c-avatar--sm" aria-hidden="true">写</span>写稿的' in grid
    )


def test_the_current_filter_chip_carries_a_tick(client, site):
    html = _main(client.get("/news/?category=guide"))
    assert '<a href="/news/?category=guide" aria-current="page">攻略</a>' in html
    chip = _block(
        INPUT_CSS.read_text(encoding="utf-8"), "\n  .c-tabs a[aria-current]::before {"
    )
    assert "mask:" in chip and "M5 12.5l4.5 4.5L19 7.5" in chip


def test_an_article_opens_with_its_author_and_ends_with_a_byline(client, site):
    news, author, guide = site
    _article(news, guide, author, title="正文页", slug="body")
    _article(news, guide, author, title="同栏目的另一篇", slug="other")
    html = _main(client.get("/news/body/"))
    meta = html[html.index('class="c-article__meta"') :]
    assert (
        '<span class="c-avatar c-avatar--sm" aria-hidden="true">写</span>' in meta[:400]
    )
    byline = html[html.index('class="c-byline"') :]
    assert "<dt>作者</dt><dd>写稿的</dd>" in byline
    related = html[html.index('class="c-related"') :]
    assert "同栏目的另一篇" in related
    # v2.0's heavy ink rules are gone from the page.
    assert "border-fg" not in html
    assert "c-facts" not in html


def test_search_is_a_filled_bar_and_groups_are_cards(client, site):
    news, author, guide = site
    _article(news, guide, author, title="内战心得", slug="s")
    html = _main(client.get("/search/?q=内战"))
    assert (
        '<form action="/search/" method="get" role="search" class="c-searchbar">'
        in html
    )
    assert "border-fg" not in html
    group = html[html.index('<section class="c-news"') :]
    assert re.search(r'<span class="c-count">\d+</span>', group)


@pytest.mark.parametrize("path", ["/news/", "/search/?q=x", "/submit/", "/privacy/"])
def test_editorial_pages_carry_no_latin_eyebrow(client, site, path):
    html = _main(client.get(path))
    for label in ("NEWS", "SEARCH", "SUBMIT", "ABOUT"):
        assert label not in html, label
