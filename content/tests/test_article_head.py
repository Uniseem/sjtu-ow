"""The article page's head, contents and end (docs/design-details.md 6;
v5.2): words and reading time, the table of contents, the author, the
articles before and after."""

import re
from datetime import timedelta

import pytest
from django.utils import timezone

from content import article_meta
from content.models import ArticleCategory, ArticlePage
from content.tests.test_content import _article, _tree, _user


def test_words_count_chinese_characters_and_latin_words():
    """6.3: no punctuation, no spaces; an English word counts as one."""
    assert article_meta.word_count("推车，不停！") == 4
    assert article_meta.word_count("用 D.Va 开团 3 次") == 6
    assert article_meta.word_count("  ，。！ ") == 0


def test_reading_time_is_400_a_minute_plus_pictures_and_videos():
    assert article_meta.reading_minutes(0) == 1
    assert article_meta.reading_minutes(400) == 1
    assert article_meta.reading_minutes(401) == 2
    assert article_meta.reading_minutes(400, images=6) == 2  # +60 s
    assert article_meta.reading_minutes(10, videos=2) == 3


def test_headings_get_numbered_anchors_and_a_list():
    html = (
        '<p>前言</p><h2 id="x">第一节</h2><h3 class="a">细节<b>一</b></h3>'
        "<h2>第二节</h2>"
    )
    anchored, headings = article_meta.anchor_headings(html)
    assert [(h.level, h.anchor, h.text) for h in headings] == [
        (2, "h-1", "第一节"),
        (3, "h-2", "细节一"),
        (2, "h-3", "第二节"),
    ]
    assert '<h2 id="h-1">第一节</h2>' in anchored
    assert '<h3 id="h-2" class="a">' in anchored
    assert 'id="x"' not in anchored


@pytest.fixture
def site(db):
    _home, news = _tree()
    return news, _user(), ArticleCategory.objects.get(slug="guide")


def _main(client, url):
    html = client.get(url).content.decode("utf-8")
    return html[html.index("<main") : html.index("</main>")]


def _body(*parts):
    return "".join(parts)  # Markdown (v6.70)


@pytest.mark.django_db
def test_the_cover_carries_the_facts(client, site):
    news, author, guide = site
    article = _article(
        news, guide, author, title="推进图", slug="push",
        body=_body("字" * 450),
    )  # fmt: skip
    main = _main(client, article.url)
    cover = main[main.index('<header class="c-cover">') : main.index("</header>")]
    assert re.search(r"约 <span[^>]*>2</span> 分钟", cover)
    assert re.search(r"<span[^>]*>450</span> 字", cover)
    assert re.search(
        r'<a href="#comments">.*<span[^>]*>0</span> 条评论</a>', cover, re.S
    )
    assert "更新于" not in cover


@pytest.mark.django_db
def test_the_counts_are_stored_at_publish_and_recounted_at_republish(client, site):
    """v7.14 (210 复核 D10): words and reading time are read off the body
    when the page is saved, not while it is shown."""
    news, author, guide = site
    article = _article(
        news, guide, author, title="存算", slug="stored",
        body=_body("**" + "字" * 450 + "**"),
    )  # fmt: skip
    article.refresh_from_db()
    assert (article.body_words, article.body_minutes) == (450, 2)
    assert article.body_plain == "字" * 450  # no markup in the stored text

    article.body = "新" * 10
    article.save_revision().publish()
    article.refresh_from_db()
    assert (article.body_words, article.body_minutes) == (10, 1)
    assert article.body_plain == "新" * 10


@pytest.mark.django_db
def test_the_head_and_cards_do_not_recount(client, site, monkeypatch):
    """Rendering a page or a card reads the stored counts (v7.14)."""
    news, author, guide = site
    article = _article(
        news, guide, author, title="不现算", slug="no-recount",
        body=_body("字" * 450),
    )  # fmt: skip

    def boom(body):
        raise AssertionError("展示时不该再算字数")

    monkeypatch.setattr(article_meta, "facts", boom)
    monkeypatch.setattr(article_meta, "stored_counts", boom)
    monkeypatch.setattr(article_meta, "body_text", boom)
    page = client.get(article.url)
    assert page.status_code == 200
    assert ">450</span> 字" in page.content.decode("utf-8")
    listing = client.get(news.url).content.decode("utf-8")
    assert "不现算" in listing and "约 <span" in listing


@pytest.mark.django_db
def test_an_edit_a_day_later_is_shown_as_updated(client, site):
    news, author, guide = site
    article = _article(news, guide, author, title="改过", slug="edited")
    ArticlePage.objects.filter(pk=article.pk).update(
        first_published_at=timezone.now() - timedelta(days=3),
        last_published_at=timezone.now(),
    )
    article.refresh_from_db()
    assert article.was_updated
    ArticlePage.objects.filter(pk=article.pk).update(
        last_published_at=article.first_published_at + timedelta(hours=20)
    )
    article.refresh_from_db()
    assert not article.was_updated


@pytest.mark.django_db
def test_contents_appear_from_three_headings(client, site):
    news, author, guide = site
    two = _article(
        news, guide, author, title="两节", slug="two",
        body=_body("## 一\n\na\n\n## 二\n\nb"),
    )  # fmt: skip
    assert "c-toc" not in _main(client, two.url)
    three = _article(
        news, guide, author, title="三节", slug="three",
        body=_body("## 一\n\na\n\n### 一点一\n\nb\n\n## 二\n\nc"),
    )  # fmt: skip
    main = _main(client, three.url)
    assert '<h2 id="h-1">一</h2>' in main
    assert main.count('<a href="#h-2">一点一</a>') == 2  # folded and side
    assert "c-toc__item--h3" in main


@pytest.mark.django_db
def test_the_end_has_the_author_and_the_articles_before_and_after(client, site):
    news, author, guide = site
    author.motto = "写点攻略"
    author.save()
    older = _article(news, guide, author, title="早一篇", slug="older")
    middle = _article(news, guide, author, title="中间", slug="middle")
    newer = _article(news, guide, author, title="晚一篇", slug="newer")
    now = timezone.now()
    for page, days in ((older, 3), (middle, 2), (newer, 1)):
        ArticlePage.objects.filter(pk=page.pk).update(
            first_published_at=now - timedelta(days=days)
        )
    main = _main(client, middle.url)
    card = main[main.index('<aside class="c-author"') : main.index("</aside>")]
    assert "“写点攻略”" in card
    assert re.search(r"在本站发表了 <span[^>]*>3</span> 篇文章", card)
    sequel = main[main.index('<nav class="c-sequel"') :]
    sequel = sequel[: sequel.index("</nav>")]
    assert sequel.index("早一篇") < sequel.index("晚一篇")
    assert "上一篇</span>" in sequel and "下一篇" in sequel
    first = _main(client, older.url)
    first_sequel = first[first.index('<nav class="c-sequel"') :]
    assert "上一篇</span>" not in first_sequel[: first_sequel.index("</nav>")]


@pytest.mark.django_db
def test_cards_name_the_author_and_the_reading_time(client, site):
    news, author, guide = site
    _article(news, guide, author, title="卡片", slug="card")
    listing = _main(client, news.url)
    card = listing[listing.index('<article class="c-media">') :]
    byline = card[card.index('<p class="c-media__byline">') :]
    byline = byline[: byline.index("</p>")]
    assert author.nickname in byline
    assert re.search(r"约 <span[^>]*>1</span> 分钟", byline)
