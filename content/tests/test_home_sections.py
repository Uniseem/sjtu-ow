"""Homepage and article pages (design 5.2). Round 065 built them after
www.sjtu.edu.cn; round 075 rebuilt them on the v2.0 design system (13.2)."""

import re
from datetime import date, datetime, timedelta

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
from tournaments.models import Tournament, TournamentStatus
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
    html = client.get("/").content.decode("utf-8")
    assert "data-carousel" not in html
    assert "carousel" not in html[html.index("</main>") :]  # nor its script


@pytest.mark.django_db
def test_the_carousel_has_a_numbered_index_and_one_caption_per_slide(client, site):
    home, *_ = site
    for index in range(3):
        HomePageCarouselItem.objects.create(
            page=home, image=_image(f"s{index}"), title=f"第{index}张", sort_order=index
        )
    html = client.get("/").content.decode("utf-8")
    assert html.count("data-caption") == 3
    assert html.count("data-dot") == 3
    assert '<span class="num">03</span>' in html
    assert html.count('aria-current="true"') == 1


# --- lists -------------------------------------------------------------------------


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


def _tournament(title, **kwargs):
    now = timezone.now()
    options = {
        "title": title,
        "registration_opens_at": now - timedelta(days=1),
        "registration_closes_at": now + timedelta(days=5),
        "status": TournamentStatus.PUBLISHED,
        "published_at": now,
    }
    options.update(kwargs)
    return Tournament.objects.create(**options)


def test_next_up_merges_by_date_and_keeps_four():
    now = timezone.now()

    class Item:
        def __init__(self, name, **dates):
            self.name = name
            self.__dict__.update(dates)

    tournaments = [
        Item("赛事5", registration_closes_at=now + timedelta(days=5)),
        Item("赛事2", registration_closes_at=now + timedelta(days=2)),
        Item("赛事9", registration_closes_at=now + timedelta(days=9)),
    ]
    scrims = [
        Item("内战1", starts_at=now + timedelta(days=1)),
        Item("内战3", starts_at=now + timedelta(days=3)),
    ]
    entries = home_data.next_up(tournaments, scrims)
    assert [entry.item.name for entry in entries] == [
        "内战1",
        "赛事2",
        "内战3",
        "赛事5",
    ]
    assert [entry.label for entry in entries] == ["开始", "截止", "开始", "截止"]


@pytest.mark.django_db
def test_the_day_strip_counts_public_scrims_and_tournament_starts():
    def at(day):
        return timezone.make_aware(datetime(2030, 5, day, 19, 0))

    make_scrim(starts_at=at(15))
    make_scrim(starts_at=at(15), status=ScrimStatus.FINISHED)
    make_scrim(starts_at=at(16), status=ScrimStatus.DRAFT)
    make_scrim(starts_at=at(17), status=ScrimStatus.CANCELLED)
    make_scrim(starts_at=at(14))  # yesterday
    make_scrim(starts_at=at(29))  # the 15th day, outside
    make_scrim(starts_at=at(28))  # the 14th day, inside
    _tournament("开赛", starts_at=at(20))
    _tournament("草稿赛", starts_at=at(21), status=TournamentStatus.DRAFT)
    _tournament("取消赛", starts_at=at(22), status=TournamentStatus.CANCELLED)

    cells = home_data.day_strip(date(2030, 5, 15))
    assert len(cells) == home_data.STRIP_DAYS == 14
    assert cells[0].date == date(2030, 5, 15) and cells[-1].date == date(2030, 5, 28)
    assert [cell.is_today for cell in cells].count(True) == 1 and cells[0].is_today
    counts = {cell.date.day: cell.count for cell in cells if cell.count}
    assert counts == {15: 2, 20: 1, 28: 1}
    assert cells[5].first_url == f"/tournaments/{cells[5].tournaments[0].pk}/"


@pytest.mark.django_db
def test_the_scrim_list_beside_the_strip_leaves_out_finished_ones():
    today = timezone.localdate()
    coming = make_scrim(title="要来的", starts_at=timezone.now() + timedelta(days=2))
    make_scrim(
        title="结束的",
        starts_at=timezone.now() + timedelta(days=2),
        status=ScrimStatus.FINISHED,
    )
    cells = home_data.day_strip(today)
    assert home_data.strip_scrims(cells) == [coming]


@pytest.mark.django_db
def test_arena_tournaments_put_open_ones_first_then_opening_soon():
    now = timezone.now()
    later = _tournament("晚截止", registration_closes_at=now + timedelta(days=9))
    sooner = _tournament("早截止", registration_closes_at=now + timedelta(days=2))
    opening = _tournament(
        "即将开放",
        registration_opens_at=now + timedelta(days=3),
        registration_closes_at=now + timedelta(days=10),
    )
    _tournament(
        "已截止",
        registration_opens_at=now - timedelta(days=9),
        registration_closes_at=now - timedelta(days=1),
    )
    _tournament("已结束", status=TournamentStatus.FINISHED)
    items = home_data.arena_tournaments()
    assert items == [("open", sooner), ("open", later), ("upcoming", opening)]
    _tournament("第四个", registration_closes_at=now + timedelta(days=4))
    assert len(home_data.arena_tournaments()) == home_data.ARENA_TOURNAMENT_COUNT


@pytest.mark.django_db
def test_the_homepage_shows_next_up_and_the_arena(client, site):
    _tournament("正在报名的赛事")
    make_scrim(title="三天后的内战", starts_at=timezone.now() + timedelta(days=3))
    html = client.get("/").content.decode("utf-8")
    assert html.count('data-next-up="tournament"') == 1
    assert html.count('data-next-up="scrim"') == 1
    arena = html[html.index('class="on-tonal l-section"') :]
    assert "正在报名的赛事" in arena and "三天后的内战" in arena
    assert "支队伍已通过" in arena
    assert 'class="c-daystrip"' in arena


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
def test_team_tiles_carry_the_member_count(client, site):
    team_services.create_team(user=player("cap@example.com", "队长"), name="图块队")
    html = client.get("/").content.decode("utf-8")
    tile = html[html.index("图块队") - 600 : html.index("图块队") + 400]
    assert "1 人" in tile


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
def test_article_body_is_set_as_prose_with_its_cover(client, site):
    _, news, author, category = site
    article = _article(
        news, category, author, title="有图", slug="with-cover", cover=_image("cv")
    )
    main = _main(client.get(article.url))
    assert '<div class="c-prose">' in main
    assert re.search(r"<figure[^>]*>\s*<img[^>]+cv", main)


@pytest.mark.django_db
def test_the_same_category_latest_leaves_out_this_article_and_others(client, site):
    _, news, author, category = site
    other = ArticleCategory.objects.get(slug="notice")
    for index in range(6):
        _article(news, category, author, title=f"同栏{index}", slug=f"same{index}")
    _article(news, other, author, title="别的栏目", slug="elsewhere")
    this = _article(news, category, author, title="本篇", slug="this")
    main = _main(client.get(this.url))
    aside = main[main.index('id="article-related"') :]
    assert "别的栏目" not in aside and "本篇" not in aside
    assert [f"同栏{i}" in aside for i in range(6)] == [
        False,
        False,
        True,
        True,
        True,
        True,
    ]
    assert aside.index("同栏5") < aside.index("同栏2")


@pytest.mark.django_db
def test_an_article_shows_its_public_tournament_as_a_ticket(client, site):
    _, news, author, category = site
    public = _tournament("关联的赛事")
    article = _article(
        news, category, author, title="带赛事", slug="t", tournament=public
    )
    main = _main(client.get(article.url))
    assert "c-ticket" in main and public.get_absolute_url() in main
    public.status = TournamentStatus.DRAFT
    public.save()
    article.save_revision().publish()
    assert "关联的赛事" not in _main(client.get(article.url))


@pytest.mark.django_db
def test_the_news_filter_marks_the_current_category(client, site):
    _, news, *_ = site
    html = client.get(news.url + "?category=guide").content.decode("utf-8")
    tabs = html[
        html.index('class="c-tabs"') : html.index(
            "</nav>", html.index('class="c-tabs"')
        )
    ]
    assert '?category=guide" aria-current="page">攻略</a>' in tabs
    assert tabs.count('aria-current="page"') == 1


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
    paragraphs spaced, not indented. v3.0 (round 081) sets quotes on a tonal
    block instead of between two rules."""
    css = (settings.BASE_DIR / "static" / "css" / "app.css").read_text()
    assert ".rich-text" not in css
    assert re.search(r"\.c-prose p\{[^}]*margin", css)
    assert not re.search(r"\.c-prose p\{[^}]*text-indent", css)
    assert re.search(r"\.c-prose blockquote\{[^}]*background-color", css)


@pytest.mark.django_db
def test_the_current_section_is_marked_in_the_navigation(client, site):
    html = client.get("/news/").content.decode("utf-8")
    assert '<a href="/news/" aria-current="page">资讯</a>' in html
    assert '<a href="/" aria-current="page">' not in html
