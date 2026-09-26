"""The 刊物 pages (design 13.2.7): v3.0 in round 083, v4.0 in round 087. The
news list as picture cards, the article page as one centred column with more
from its category after it, the about pages, search."""

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


def test_the_news_list_is_a_grid_of_picture_cards(client, site):
    news, author, guide = site
    _article(news, guide, author, title="有封面", slug="c", cover=_image("c"))
    _article(news, guide, author, title="没封面", slug="p", summary="两行摘要")
    notice = ArticleCategory.objects.get(slug="notice")
    _article(news, notice, author, title="公告没封面", slug="n")
    html = _main(client.get("/news/"))
    grid = html[html.index('class="c-media-grid c-media-grid--3"') :]
    cards = grid.split('<article class="c-media">')[1:]
    assert len(cards) == 3
    covered = next(card for card in cards if ">有封面<" in card)
    assert "<img" in covered and "c-media__none" not in covered
    # No cover: the category's name on the second surface (13.2.5), no pattern.
    plain = next(card for card in cards if ">没封面<" in card)
    assert '<span class="c-media__none">攻略</span>' in plain
    other = next(card for card in cards if ">公告没封面<" in card)
    assert '<span class="c-media__none">公告</span>' in other
    # The list shows the summary (5.2); the homepage cards do not.
    assert '<p class="c-media__summary">两行摘要</p>' in plain
    assert "c-hatch" not in grid


def test_the_current_filter_is_underlined_in_red(client, site):
    html = _main(client.get("/news/?category=guide"))
    assert '<a href="/news/?category=guide" aria-current="page">攻略</a>' in html
    rule = _block(
        INPUT_CSS.read_text(encoding="utf-8"),
        '\n  .c-tabs a[aria-current="page"]::after,',
    )
    assert "height: 2px;" in rule
    assert "background-color: var(--color-primary);" in rule


def test_an_article_is_one_centred_column_with_more_after_it(client, site):
    news, author, guide = site
    _article(news, guide, author, title="正文页", slug="body")
    _article(news, guide, author, title="同栏目的另一篇", slug="other")
    html = _main(client.get("/news/body/"))
    meta = html[html.index('class="c-article__meta"') :]
    assert (
        '<span class="c-avatar c-avatar--sm" aria-hidden="true">写</span>' in meta[:400]
    )
    article = html[html.index('<article class="c-article">') : html.index("</article>")]
    assert "同栏目的另一篇" not in article
    more = html[html.index('aria-labelledby="article-related"') :]
    assert "同栏目的另一篇" in more and '<article class="c-media">' in more
    column = _block(INPUT_CSS.read_text(encoding="utf-8"), "\n  .c-article {")
    assert "max-width: calc(var(--container-prose) + 2rem);" in column
    assert "margin-inline: auto;" in column
    assert "c-byline" not in html and "c-related" not in html


def test_the_about_pages_switch_with_one_row_of_links(client, site):
    html = _main(client.get("/privacy/"))
    tabs = html[html.index('<nav class="c-tabs"') : html.index("</nav>")]
    for path in ("/about/", "/terms/", "/privacy/"):
        assert f'<a href="{path}"' in tabs
    assert '<a href="/privacy/" aria-current="page">隐私政策</a>' in tabs
    assert tabs.count('aria-current="page"') == 1
    assert "c-sidenav" not in html


def test_search_groups_are_plain_rows_without_small_print(client, site):
    news, author, guide = site
    _article(news, guide, author, title="内战心得", slug="s")
    html = _main(client.get("/search/?q=内战"))
    assert (
        '<form action="/search/" method="get" role="search" class="c-searchbar">'
        in html
    )
    assert re.search(r'<li class="c-row c-row--plain">', html)
    assert "c-count" not in html
    assert "c-pagehead__meta" not in html


def test_quotes_are_a_rule_not_a_filled_block():
    rule = _block(INPUT_CSS.read_text(encoding="utf-8"), "\n  .c-prose blockquote {")
    assert "border-left: 3px solid var(--color-line);" in rule
    assert "background" not in rule


@pytest.mark.parametrize("path", ["/news/", "/search/?q=x", "/submit/", "/privacy/"])
def test_editorial_pages_carry_no_latin_eyebrow(client, site, path):
    html = _main(client.get(path))
    for label in ("NEWS", "SEARCH", "SUBMIT", "ABOUT"):
        assert label not in html, label
