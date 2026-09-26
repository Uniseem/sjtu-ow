"""Homepage and article pages (design 5.2). Round 065 built them after
www.sjtu.edu.cn; round 075 rebuilt them on the v2.0 design system; round 082
on v3.0 (the M mockup): hero, key figures, 近期安排, quick entries, 资讯,
通知公告, 活动统计, 战队."""

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
    assert "carousel" not in html
    assert "c-feature" not in html and "c-daystrip" not in html


# --- hero: key figures (5.2, 13.2.6) ---


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
    figures = html[html.index('class="c-figures"') : html.index("</dl>")]
    cell = figures[figures.index(f"<dt>{label}</dt>") :]
    return cell[: cell.index("</div>")]


@pytest.mark.django_db
def test_the_hero_counts_joined_members_and_live_teams(client, site):
    joined = player("joined@example.com", "已加入")
    EmailAddress.objects.create(user=joined, email=joined.email, verified=True)
    player("unverified@example.com", "没验证")
    gone = team_services.create_team(user=joined, name="解散的队")
    team_services.disband_team(team=gone, actor=joined)
    team_services.create_team(user=joined, name="一支队")
    html = _main(client.get("/"))
    members = home_data.member_count()
    assert members == 1 + 0  # the editor from the fixture has no verified email
    assert f'data-count-to="{members}"' in _figure(html, "注册成员")
    assert home_data.team_count() == 1
    assert 'data-count-to="1"' in _figure(html, "战队")


@pytest.mark.django_db
def test_the_age_figure_only_shows_once_a_founding_date_is_set(client, site):
    assert 'data-figure="age"' not in _main(client.get("/"))
    _settings(founded_on=timezone.localdate() - timedelta(days=400))
    cell = _figure(_main(client.get("/")), "社区已成立")
    assert "<small>年</small>" in cell and "<small>天</small>" in cell


@pytest.mark.django_db
def test_the_hero_carries_the_emblem_as_a_watermark(client, site):
    html = _main(client.get("/"))
    hero = html[html.index('class="c-hero"') : html.index('class="l-container c-quick')]
    assert re.search(
        r'<img class="c-hero__emblem-img" '
        r'src="/static/img/sjtu-emblem[^"]*\.svg" alt=""',
        hero,
    )
    assert '<div class="c-hero__emblem" aria-hidden="true" data-parallax' in hero
    assert "<h1" in hero and "守望先锋社区" in hero


# --- quick entries ---


def _quick(html):
    start = html.index('class="l-container c-quick"')
    return html[start : html.index("</nav>", start)]


@pytest.mark.django_db
def test_quick_entries_link_where_they_say(client, site):
    quick = _quick(_main(client.get("/")))
    for href, label in (
        ("/tournaments/", "赛事报名"),
        ("/scrims/", "内战报名"),
        ("/teams/", "找战队"),
        ("/members/", "成员展示"),
        ("/submit/", "投稿"),
    ):
        assert f'<a href="{href}" class="c-quick__tile' in quick, href
        assert f"<b>{label}</b>" in quick
    assert "QQ" not in quick


def test_the_qq_link_must_be_https():
    for bad in ("http://qm.qq.com/q/abc", "javascript:alert(1)"):
        with pytest.raises(ValidationError):
            SiteSettings(qq_group_url=bad).clean_fields(exclude=SECRET_FIELDS)
    SiteSettings(qq_group_url="https://qm.qq.com/q/abc").clean_fields(
        exclude=SECRET_FIELDS
    )


@pytest.mark.django_db
def test_the_qq_tile_appears_once_a_link_is_set(client, site):
    _settings(qq_group_url="https://qm.qq.com/q/abc")
    quick = _quick(_main(client.get("/")))
    assert (
        '<a href="https://qm.qq.com/q/abc" class="c-quick__tile c-quick__tile--mint"'
        in quick
    )
    assert "<b>加入 QQ 群</b>" in quick


# --- 近期安排 ---


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
def test_the_agenda_card_shows_signups_against_what_a_match_needs(client, site):
    _tournament("正在报名的赛事")
    scrim = make_scrim(
        title="三天后的内战", starts_at=timezone.now() + timedelta(days=3)
    )
    _sign_up(scrim, player("signer@example.com", "报名的人"))
    html = _main(client.get("/"))
    agenda = html[html.index('class="c-agenda"') : html.index("</aside>")]
    assert agenda.count('data-next-up="tournament"') == 1
    assert agenda.count('data-next-up="scrim"') == 1
    needed = scrim.players_needed
    assert f'<progress value="1" max="{needed}"' in agenda
    assert f"已报 <b>1</b> / {needed}" in agenda
    assert "已通过 <b>0</b> 队" in agenda
    # Tournaments have no team cap, so no progress bar for them (5.2).
    assert agenda.count("<progress") == 1


@pytest.mark.django_db
def test_an_empty_agenda_says_so(client, site):
    assert "最近没有安排" in _main(client.get("/"))


# --- 资讯, 通知公告, 活动统计 ---


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
def test_the_news_card_leads_with_one_and_lists_five(client, site):
    _, news, author, category = site
    for index in range(7):
        _article(news, category, author, title=f"文章{index}", slug=f"a{index}")
    html = _main(client.get("/"))
    card = html[html.index('class="c-news"') : html.index('class="c-homeside"')]
    assert card.count('class="c-news__lead"') == 1
    assert card.count('class="c-news__row"') == home_data.LATEST_ARTICLE_COUNT - 1
    assert "文章6" in card[card.index("c-news__lead") : card.index("c-news__list")]


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


@pytest.mark.django_db
def test_activity_stats_count_what_is_finished(client, site):
    now = timezone.now()
    make_scrim(status=ScrimStatus.FINISHED, starts_at=now - timedelta(days=3))
    make_scrim(status=ScrimStatus.FINISHED, starts_at=now - timedelta(days=9))
    make_scrim()  # published, not yet held
    _tournament("办完的", status=TournamentStatus.FINISHED)
    _tournament("报名中的")
    assert home_data.activity_stats() == {"scrims": 2, "tournaments": 1}
    html = _main(client.get("/"))
    stats = html[html.index('class="c-stats"') :]
    assert '<dt>累计内战</dt><dd><span data-count-to="2">2</span>' in stats
    assert '<dt>举办赛事</dt><dd><span data-count-to="1">1</span>' in stats


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
def test_the_two_homepage_settings_refresh_it_and_the_others_do_not(prerender_on):
    SiteSettings.load()
    PrerenderedPage.objects.all().delete()
    _settings(scrim_reminder_hours=3)
    assert "/" not in _requested()
    _settings(founded_on=date(2023, 5, 24))
    assert "/" in _requested()
    PrerenderedPage.objects.all().delete()
    _settings(qq_group_url="https://qm.qq.com/q/abc")
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
    assert "1 名成员" in tile


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
