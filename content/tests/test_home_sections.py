"""Homepage and article pages after www.sjtu.edu.cn (round 065, design 5.2)."""

import re
from datetime import date, datetime

import pytest
from django.core.exceptions import ValidationError
from django.utils import timezone

from content import home as home_data
from content.models import ArticleCategory, HomePageCarouselItem
from content.tests.test_content import _article, _image, _tree, _user
from core.models import PrerenderedPage
from scrims.models import ScrimStatus
from scrims.tests.test_scrims import make_scrim
from teams import services as team_services
from tournaments.tests.test_state_table import player


def _main(response):
    html = response.content.decode("utf-8")
    return html[html.index("<main") : html.index("</main>")]


@pytest.fixture
def site(db):
    home, news = _tree()
    return home, news, _user(), ArticleCategory.objects.get(slug="guide")


# --- carousel --------------------------------------------------------------------


def test_the_admins_slides_come_in_their_order(site):
    home, news, author, category = site
    page = _article(news, category, author, title="赛事公告", slug="notice")
    HomePageCarouselItem.objects.create(
        page=home, image=_image("b"), title="第二张", sort_order=1
    )
    HomePageCarouselItem.objects.create(
        page=home, image=_image("a"), title="第一张", link_page=page, sort_order=0
    )
    slides = home_data.carousel_slides(home)
    assert [slide.title for slide in slides] == ["第一张", "第二张"]
    assert slides[0].url == page.url


def test_without_slides_the_latest_articles_with_a_cover_are_used(site):
    home, news, author, category = site
    _article(news, category, author, title="没有封面", slug="plain")
    _article(news, category, author, title="有封面", slug="covered", cover=_image("c"))
    assert [slide.title for slide in home_data.carousel_slides(home)] == ["有封面"]


def test_a_slide_to_an_unpublished_page_falls_back_to_its_address(site):
    home, news, author, category = site
    hidden = _article(news, category, author, title="草稿", slug="draft", live=False)
    item = HomePageCarouselItem(
        page=home, title="x", link_page=hidden, link_url="/tournaments/"
    )
    assert item.url == "/tournaments/"


@pytest.mark.parametrize(
    "url", ["javascript:alert(1)", "//evil.example/", "http://example.com/"]
)
def test_slide_links_must_be_site_paths_or_https(url):
    with pytest.raises(ValidationError, match="站内地址以 / 开头"):
        HomePageCarouselItem(title="x", link_url=url).clean()


@pytest.mark.parametrize("url", ["/tournaments/3/", "https://example.com/", ""])
def test_site_paths_and_https_links_are_accepted(url):
    HomePageCarouselItem(title="x", link_url=url).clean()


@pytest.mark.django_db
def test_the_homepage_shows_the_carousel_and_loads_its_script(client, site):
    home, *_ = site
    HomePageCarouselItem.objects.create(
        page=home, image=_image("a"), title="秋季赛开始报名"
    )
    html = client.get("/").content.decode("utf-8")
    assert "data-carousel" in html
    assert "秋季赛开始报名" in html
    assert re.search(r'<script src="/static/js/carousel[^"]*\.js"', html)


@pytest.mark.django_db
def test_no_pictures_means_no_carousel(client, site):
    assert "data-carousel" not in client.get("/").content.decode("utf-8")


# --- lists -------------------------------------------------------------------------


def test_picture_news_only_shows_articles_with_a_cover(site):
    _, news, author, category = site
    _article(news, category, author, title="没有封面", slug="plain")
    for index in range(5):
        _article(
            news,
            category,
            author,
            title=f"图{index}",
            slug=f"pic{index}",
            cover=_image(f"p{index}"),
        )
    titles = [article.title for article in home_data.picture_news()]
    assert titles == ["图4", "图3", "图2", "图1"]


def test_pinned_articles_lead_the_news_list_without_repeats(site):
    _, news, author, category = site
    for index in range(8):
        _article(news, category, author, title=f"新{index}", slug=f"new{index}")
    # Pin the newest, so it is also in the latest list and could repeat.
    pinned = _article(news, category, author, title="置顶", slug="pinned")
    items = home_data.news_list([pinned])
    assert items[0] == pinned
    assert len(items) == home_data.LATEST_ARTICLE_COUNT
    assert len({article.pk for article in items}) == len(items)


def test_event_cards_put_tournaments_first_and_fill_one_row():
    cards = home_data.event_cards(["赛事甲", "赛事乙"], ["内战甲", "内战乙"])
    assert cards == [
        ("tournament", "赛事甲"),
        ("tournament", "赛事乙"),
        ("scrim", "内战甲"),
    ]


# --- calendar ------------------------------------------------------------------------


@pytest.mark.django_db
def test_the_calendar_marks_days_with_public_scrims():
    def at(month, day):
        return timezone.make_aware(datetime(2030, month, day, 19, 0))

    make_scrim(starts_at=at(5, 10))
    make_scrim(starts_at=at(5, 12), status=ScrimStatus.DRAFT)
    make_scrim(starts_at=at(5, 14), status=ScrimStatus.CANCELLED)
    make_scrim(starts_at=at(5, 20), status=ScrimStatus.FINISHED)
    make_scrim(starts_at=at(6, 1))

    calendar = home_data.scrim_calendar(date(2030, 5, 15))
    days = [day for week in calendar["weeks"] for day in week]
    assert {day.day for day in days if day.has_event} == {10, 20}
    assert [day.day for day in days if day.is_today] == [15]
    # 2030-05-01 is a Wednesday; weeks start on Monday.
    assert [day.in_month for day in calendar["weeks"][0][:3]] == [False, False, True]


# --- teams ---------------------------------------------------------------------------


@pytest.fixture
def prerender_on(settings, tmp_path):
    settings.PRERENDER_ENABLED = True
    settings.PRERENDER_ROOT = tmp_path


@pytest.mark.django_db
def test_a_new_team_refreshes_the_homepage(prerender_on):
    team_services.create_team(user=player("cap@example.com", "队长"), name="新战队")
    assert "/" in set(PrerenderedPage.objects.values_list("path", flat=True))


@pytest.mark.django_db
def test_disbanded_teams_leave_the_homepage():
    captain = player("cap@example.com", "队长")
    kept = team_services.create_team(user=captain, name="留下的")
    gone = team_services.create_team(user=player("b@example.com", "乙"), name="解散的")
    team_services.disband_team(team=gone, actor=gone.captain())
    assert home_data.teams() == [kept]


# --- article pages ------------------------------------------------------------------


@pytest.mark.django_db
def test_article_pages_leave_the_summary_to_lists(client, site):
    _, news, author, category = site
    article = _article(
        news, category, author, title="文章", slug="a", summary="列表用的摘要"
    )
    # The summary stays in <meta name="description">; the page body leaves it out.
    assert "列表用的摘要" not in _main(client.get(article.url))
    assert "列表用的摘要" in _main(client.get(news.url))


@pytest.mark.django_db
def test_a_quote_names_its_source(client, site):
    _, news, author, category = site
    article = _article(
        news,
        category,
        author,
        title="有引用",
        slug="q",
        body=[("quote", {"text": "一起进步。", "attribution": "社团负责人"})],
    )
    html = client.get(article.url).content.decode("utf-8")
    assert re.search(
        r"<blockquote>\s*<p>一起进步。</p>\s*<footer>——社团负责人</footer>", html
    )


def test_body_text_rules_match_what_wagtail_renders(settings):
    """Wagtail does not wrap rich text in .rich-text, so rules keyed on it never
    applied: paragraphs, lists and links in articles had no styling (round 065).
    Round 074 moved body text to the design system's c-prose (design 13.2.7):
    paragraphs spaced, not indented; quotes between two rules."""
    css = (settings.BASE_DIR / "static" / "css" / "app.css").read_text()
    assert ".rich-text" not in css
    assert re.search(r"\.c-prose p\{[^}]*margin", css)
    assert not re.search(r"\.c-prose p\{[^}]*text-indent", css)
    assert re.search(r"\.c-prose blockquote\{[^}]*border-top", css)


@pytest.mark.django_db
def test_the_current_section_is_marked_in_the_navigation(client, site):
    html = client.get("/news/").content.decode("utf-8")
    assert '<a href="/news/" aria-current="page">资讯</a>' in html
    assert '<a href="/" aria-current="page">' not in html
