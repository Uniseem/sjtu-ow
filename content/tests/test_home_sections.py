"""Homepage and article pages (design 5.2). Round 065 built them after
www.sjtu.edu.cn; rounds 075 and 082 rebuilt them on v2.0 and v3.0; round 086
on v4.0: the hero picture, the figures row, 近期 (the open tournament and this
week's scrims), 资讯 with 公告, 战队."""

import re
from datetime import date, timedelta

import pytest
from allauth.account.models import EmailAddress
from django.core.exceptions import ValidationError
from django.utils import timezone

import content.models
from content import home as home_data
from content.models import ArticleCategory
from content.tests.test_content import _article, _image, _tree, _user
from core.models import PrerenderedPage, SiteSettings
from scrims import services as scrim_services
from scrims.models import ScrimStatus
from scrims.tests.test_scrims import make_scrim
from teams import services as team_services
from tournaments.models import Tournament, TournamentStatus
from tournaments.tests.test_state_table import player

# SiteSettings.clean_fields would try to decrypt the empty secret fields.
SECRET_FIELDS = ["smtp_password", "backup_s3_secret_access_key"]


def _main(response):
    html = response.content.decode("utf-8")
    return html[html.index("<main") : html.index("</main>")]


@pytest.fixture
def site(db):
    home, news = _tree()
    return home, news, _user(), ArticleCategory.objects.get(slug="guide")


@pytest.fixture
def prerender_on(settings, tmp_path):
    settings.PRERENDER_ENABLED = True
    settings.PRERENDER_ROOT = tmp_path


def _requested():
    return set(PrerenderedPage.objects.values_list("path", flat=True))


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


def _settings(**fields):
    site = SiteSettings.load()
    for name, value in fields.items():
        setattr(site, name, value)
    site.save()


def _sign_up(scrim, user):
    scrim_services.sign_up(
        scrim=scrim,
        user=user,
        game_account_id=user.game_accounts.first().pk,
        roles=["damage"],
    )


# --- 焦点图 is gone (v3.0) ---


def test_the_carousel_model_is_gone():
    assert not hasattr(content.models, "HomePageCarouselItem")


@pytest.mark.django_db
def test_the_homepage_loads_no_carousel(client, site):
    html = client.get("/").content.decode("utf-8")
    assert "carousel" not in html and "c-daystrip" not in html


# --- the figures row (5.2) ---


@pytest.mark.parametrize(
    ("founded", "today", "expected"),
    [
        (date(2023, 5, 24), date(2026, 9, 26), (3, 125)),
        (date(2024, 10, 1), date(2026, 9, 26), (1, 360)),  # before this year's
        (date(2026, 9, 26), date(2026, 9, 26), (0, 0)),  # founded today
        (date(2024, 2, 29), date(2025, 2, 27), (0, 364)),
        (date(2024, 2, 29), date(2025, 2, 28), (1, 0)),  # 29 Feb falls on the 28th
        (date(2024, 2, 29), date(2025, 3, 1), (1, 1)),
    ],
)
def test_community_age_counts_whole_years_then_days(founded, today, expected):
    age = home_data.community_age(founded, today)
    assert (age.years, age.days) == expected


def test_no_date_or_a_future_date_gives_no_age():
    assert home_data.community_age(None, date(2026, 9, 26)) is None
    assert home_data.community_age(date(2026, 9, 27), date(2026, 9, 26)) is None


def _figure(html, label):
    start = html.index('class="l-container c-stats__list"')
    figures = html[start : html.index("</dl>", start)]
    cell = figures[figures.index(f"<dt>{label}</dt>") :]
    return cell[: cell.index("</div>")]


@pytest.mark.django_db
def test_the_figures_count_joined_members_and_live_teams(client, site):
    joined = player("joined@example.com", "已加入")
    EmailAddress.objects.create(user=joined, email=joined.email, verified=True)
    player("unverified@example.com", "没验证")
    gone = team_services.create_team(user=joined, name="解散的队")
    team_services.disband_team(team=gone, actor=joined)
    team_services.create_team(user=joined, name="一支队")
    html = _main(client.get("/"))
    members = home_data.member_count()
    assert members == 1 + 0  # the editor from the fixture has no verified email
    assert f"<dd>{members}</dd>" in _figure(html, "注册成员")
    assert home_data.team_count() == 1
    assert "<dd>1</dd>" in _figure(html, "战队")


@pytest.mark.django_db
def test_the_age_figure_only_shows_once_a_founding_date_is_set(client, site):
    assert 'data-figure="age"' not in _main(client.get("/"))
    _settings(founded_on=timezone.localdate() - timedelta(days=400))
    cell = _figure(_main(client.get("/")), "社区已成立")
    assert re.search(r"<dd>1 年 \d+ 天</dd>", cell)


@pytest.mark.django_db
def test_the_figures_count_finished_scrims(client, site):
    now = timezone.now()
    make_scrim(status=ScrimStatus.FINISHED, starts_at=now - timedelta(days=3))
    make_scrim(status=ScrimStatus.FINISHED, starts_at=now - timedelta(days=9))
    make_scrim()  # published, not yet held
    assert home_data.scrims_held() == 2
    assert "<dd>2</dd>" in _figure(_main(client.get("/")), "累计内战")


# --- the hero (5.2, 13.2.5) ---


def _hero(html):
    return html[html.index('<section class="c-hero') : html.index("</section>")]


@pytest.mark.django_db
def test_the_hero_shows_the_uploaded_picture_or_else_the_emblem(client, site):
    hero = _hero(_main(client.get("/")))
    assert '<section class="c-hero c-hero--plain"' in hero
    assert re.search(r'<img class="c-hero__emblem" src="/static/img/sjtu-emblem', hero)
    assert "<h1" in hero and "守望先锋社区" in hero
    _settings(hero_image=_image("hero"))
    hero = _hero(_main(client.get("/")))
    assert "c-hero--plain" not in hero and "c-hero__emblem" not in hero
    assert 'class="c-hero__img"' in hero


@pytest.mark.django_db
def test_the_hero_has_one_primary_action_and_the_qq_button_once_set(client, site):
    hero = _hero(_main(client.get("/")))
    assert hero.count("c-btn--primary") == 1
    assert 'href="/accounts/signup/" class="c-btn c-btn--primary">加入社区</a>' in hero
    assert "QQ" not in hero
    _settings(qq_group_url="https://qm.qq.com/q/abc")
    hero = _hero(_main(client.get("/")))
    assert '<a href="https://qm.qq.com/q/abc" class="c-btn c-btn--light"' in hero


def test_the_qq_link_must_be_https():
    for bad in ("http://qm.qq.com/q/abc", "javascript:alert(1)"):
        with pytest.raises(ValidationError):
            SiteSettings(qq_group_url=bad).clean_fields(exclude=SECRET_FIELDS)
    SiteSettings(qq_group_url="https://qm.qq.com/q/abc").clean_fields(
        exclude=SECRET_FIELDS
    )


# --- 近期 ---


@pytest.mark.django_db
def test_the_feature_is_the_tournament_that_closes_soonest(site):
    now = timezone.now()
    later = _tournament("晚截止", registration_closes_at=now + timedelta(days=9))
    sooner = _tournament("早截止", registration_closes_at=now + timedelta(days=2))
    assert home_data.feature_tournament([later, sooner]).tournament == sooner
    assert home_data.feature_tournament([]) is None


@pytest.mark.django_db
def test_scrim_rows_keep_the_first_four_by_start(site):
    now = timezone.now()
    scrims = [
        make_scrim(title=f"内战{day}", starts_at=now + timedelta(days=day))
        for day in (5, 1, 3, 2, 4)
    ]
    rows = home_data.scrim_rows(scrims)
    assert [row.scrim.title for row in rows] == ["内战1", "内战2", "内战3", "内战4"]
    assert all(row.capacity == row.scrim.players_needed for row in rows)


@pytest.mark.django_db
def test_upcoming_shows_the_open_tournament_and_scrim_signups(client, site):
    _tournament("正在报名的赛事")
    scrim = make_scrim(
        title="三天后的内战", starts_at=timezone.now() + timedelta(days=3)
    )
    _sign_up(scrim, player("signer@example.com", "报名的人"))
    html = _main(client.get("/"))
    start = html.index('aria-labelledby="home-upcoming"')
    upcoming = html[start : html.index("</section>", start)]
    assert upcoming.count('data-next-up="tournament"') == 1
    assert upcoming.count('data-next-up="scrim"') == 1
    needed = scrim.players_needed
    assert f'<progress class="c-meter" value="1" max="{needed}"' in upcoming
    assert f"已报 1 / {needed}" in upcoming
    assert "已通过 0 队" in upcoming
    # Tournaments have no team cap, so no progress bar for them (5.2).
    assert upcoming.count("<progress") == 1


@pytest.mark.django_db
def test_an_empty_agenda_says_so(client, site):
    assert "最近没有安排" in _main(client.get("/"))


# --- 资讯 and 公告 ---


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


@pytest.mark.django_db
def test_the_news_block_is_four_picture_cards_newest_first(client, site):
    _, news, author, category = site
    for index in range(7):
        _article(news, category, author, title=f"文章{index}", slug=f"a{index}")
    html = _main(client.get("/"))
    start = html.index('class="c-media-grid"')
    grid = html[start : html.index('aria-labelledby="home-notices"')]
    assert grid.count('<article class="c-media">') == home_data.LATEST_ARTICLE_COUNT
    assert grid.index("文章6") < grid.index("文章5")


@pytest.mark.django_db
def test_notices_take_only_the_two_official_categories(site):
    _, news, author, guide = site
    notice = ArticleCategory.objects.get(slug="notice")
    event = ArticleCategory.objects.get(slug="event-notice")
    for index in range(4):
        _article(news, notice, author, title=f"公告{index}", slug=f"n{index}")
    for index in range(3):
        _article(news, event, author, title=f"赛事通知{index}", slug=f"e{index}")
    # The newest article of all is a guide; it must still stay out.
    _article(news, guide, author, title="攻略文", slug="g")
    items = home_data.notices()
    assert len(items) == home_data.NOTICE_COUNT == 5
    assert {item.category.slug for item in items} <= {"notice", "event-notice"}
    assert items[0].title == "赛事通知2"  # newest first


# --- the homepage is regenerated when what it prints changes (13.13.4) ---


@pytest.mark.django_db
def test_a_scrim_signup_refreshes_the_homepage(prerender_on):
    scrim = make_scrim()
    signer = player("signer@example.com", "报名的人")
    PrerenderedPage.objects.all().delete()
    _sign_up(scrim, signer)
    assert "/" in _requested()


@pytest.mark.django_db
def test_a_verified_email_refreshes_the_homepage(prerender_on):
    user = player("new@example.com", "新人")
    PrerenderedPage.objects.all().delete()
    EmailAddress.objects.create(user=user, email=user.email, verified=True)
    assert "/" in _requested()


@pytest.mark.django_db
def test_deactivating_an_account_refreshes_the_homepage(prerender_on):
    user = player("leaving@example.com", "要走的")
    PrerenderedPage.objects.all().delete()
    user.is_active = False
    user.save()
    assert "/" in _requested()


@pytest.mark.django_db
def test_the_homepage_settings_refresh_it_and_the_others_do_not(prerender_on):
    SiteSettings.load()
    PrerenderedPage.objects.all().delete()
    _settings(scrim_reminder_hours=3)
    assert "/" not in _requested()
    _settings(founded_on=date(2023, 5, 24))
    assert "/" in _requested()
    PrerenderedPage.objects.all().delete()
    _settings(qq_group_url="https://qm.qq.com/q/abc")
    assert "/" in _requested()
    PrerenderedPage.objects.all().delete()
    _settings(hero_image=_image("hero"))
    assert "/" in _requested()


# --- teams ---


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


# --- article pages ---


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
