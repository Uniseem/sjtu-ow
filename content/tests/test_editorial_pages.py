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
    assert "<img" in covered and "img/placeholders/" not in covered
    # No cover: the article's own placeholder picture (13.2.5, round 090),
    # a different one for each article.
    plain = next(card for card in cards if ">没封面<" in card)
    other = next(card for card in cards if ">公告没封面<" in card)
    pictures = [
        re.search(r'<img src="([^"]*img/placeholders/cover-\d\d\.svg)"', card)
        for card in (plain, other)
    ]
    assert all(pictures)
    assert pictures[0].group(1) != pictures[1].group(1)
    # The list shows the summary (5.2); the homepage cards do not.
    assert '<p class="c-media__summary">两行摘要</p>' in plain
    assert "c-hatch" not in grid


def test_the_current_filter_is_underlined_in_orange(client, site):
    """v5.0: where you are is Overwatch orange (13.2.1 #2)."""
    html = _main(client.get("/news/?category=guide"))
    assert '<a href="/news/?category=guide" aria-current="page">攻略</a>' in html
    rule = _block(
        INPUT_CSS.read_text(encoding="utf-8"),
        '\n  .c-tabs a[aria-current="page"]::after,',
    )
    assert "height: 2px;" in rule
    assert "background-color: var(--color-accent);" in rule


def test_an_article_is_one_centred_column_with_more_after_it(client, site):
    news, author, guide = site
    _article(news, guide, author, title="正文页", slug="body")
    _article(news, guide, author, title="同栏目的另一篇", slug="other")
    html = _main(client.get("/news/body/"))
    meta = html[html.index('c-article__meta"') :]
    # The author's initial in their own tint (v5.2), in the cover's facts.
    hue = author.pk % 5 + 1
    assert (
        f'<span class="c-avatar c-avatar--xs c-hue-{hue}" aria-hidden="true">写</span>'
    ) in meta[:400]
    article = html[html.index('<article class="c-article">') : html.index("</article>")]
    # Only as the article before this one (design-details 6.6); the cards of
    # the same category come after the article.
    assert "同栏目的另一篇" not in article.split('<nav class="c-sequel"')[0]
    more = html[html.index('aria-labelledby="article-related"') :]
    assert "同栏目的另一篇" in more and '<article class="c-media">' in more
    # v5.2: the reading column is centred; the head is centred on it.
    css = INPUT_CSS.read_text(encoding="utf-8")
    column = _block(css, "\n  .c-article > * {")
    assert "max-width: var(--container-prose);" in column
    assert "margin-inline: auto;" in column
    head = _block(css, "\n  .c-article__head {")
    assert "text-align: center;" in head and "justify-items: center;" in head
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
