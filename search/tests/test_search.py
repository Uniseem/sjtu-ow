"""Design 13.16: site search over four kinds of public content (round 071)."""

from datetime import timedelta

import pytest
from django.core.cache import cache
from django.urls import reverse
from django.utils import timezone

from content.models import ArticleCategory
from content.tests.test_content import _article, _tree
from members.tests.test_members import person
from scrims.models import Scrim, ScrimStatus
from search import services
from teams import services as team_services
from tournaments.models import Tournament, TournamentStatus

# --- the query and the excerpt -----------------------------------------------------


def test_parse_query_splits_folds_and_caps():
    assert services.parse_query("  Genji  守望 ") == ["genji", "守望"]
    assert services.parse_query("") == []
    assert services.parse_query(None) == []
    assert services.parse_query("a b c d e f g") == ["a", "b", "c", "d", "e"]
    assert len("".join(services.parse_query("x" * 80))) == 50


def test_excerpt_surrounds_the_first_hit():
    text = "前面" * 60 + "命中词" + "后面" * 60
    piece = services.excerpt(text, ["命中词"])
    assert piece.startswith("…") and piece.endswith("…")
    assert "命中词" in piece
    assert len(piece) <= 2 * services.EXCERPT_RADIUS + 2


def test_excerpt_strips_tags_and_falls_back_to_the_head():
    piece = services.excerpt("<p>没有命中</p><p>的段落</p>", ["别的"])
    assert "<p>" not in piece
    assert piece.startswith("没有命中的段落")


def test_every_term_must_match():
    assert services.matches("交大守望先锋社区", ["交大", "社区"])
    assert not services.matches("交大守望先锋社区", ["交大", "复旦"])
    assert not services.matches("anything", [])


# --- articles ------------------------------------------------------------------------


@pytest.fixture
def articles(db):
    _home, news = _tree()
    category = ArticleCategory.objects.get(slug="guide")
    author = person("作者")
    live = _article(
        news,
        category,
        author,
        title="源氏教学",
        slug="genji-guide",
        summary="一篇摘要",
        body=[("paragraph", "<p>正文里提到了<strong>龙刃</strong>的时机。</p>")],
    )
    draft = _article(
        news, category, author, title="未发布的龙刃心得", slug="draft-guide", live=False
    )
    return live, draft


@pytest.mark.django_db
def test_articles_match_title_summary_and_body(articles):
    live, _draft = articles

    for term in ("源氏", "摘要", "龙刃"):
        group = services.search_articles([term])
        assert [hit.title for hit in group.hits] == [live.title], term
    hit = services.search_articles(["龙刃"]).hits[0]
    assert hit.url == live.get_url()
    assert hit.meta == "攻略"
    assert "<strong>" not in hit.excerpt and "龙刃" in hit.excerpt


@pytest.mark.django_db
def test_unpublished_articles_are_invisible(articles):
    assert services.search_articles(["未发布"]).hits == []


# --- events ---------------------------------------------------------------------------


def _tournament(title, status=TournamentStatus.PUBLISHED):
    now = timezone.now()
    return Tournament.objects.create(
        title=title,
        summary="校内邀请赛",
        description="<p>详细<em>规则</em>见群公告</p>",
        registration_opens_at=now - timedelta(days=1),
        registration_closes_at=now + timedelta(days=7),
        roster_min=2,
        roster_max=5,
        status=status,
        published_at=now if status != TournamentStatus.DRAFT else None,
    )


@pytest.mark.django_db
def test_events_include_published_tournaments_and_scrims_only():
    _tournament("公开的秋季赛")
    _tournament("草稿赛事", TournamentStatus.DRAFT)
    _tournament("取消的赛事", TournamentStatus.CANCELLED)
    _tournament("结束的赛事", TournamentStatus.FINISHED)
    Scrim.objects.create(
        title="周五内战",
        description="轻松局",
        starts_at=timezone.now() + timedelta(days=1),
        status=ScrimStatus.PUBLISHED,
    )
    Scrim.objects.create(
        title="草稿内战",
        starts_at=timezone.now() + timedelta(days=1),
        status=ScrimStatus.DRAFT,
    )

    titles = {hit.title for hit in services.search_events(["赛"]).hits}
    assert titles == {"公开的秋季赛", "结束的赛事"}
    scrim_hits = services.search_events(["内战"]).hits
    assert [hit.title for hit in scrim_hits] == ["周五内战"]
    assert scrim_hits[0].meta == "内战"
    rule_hits = services.search_events(["规则"]).hits
    assert {hit.title for hit in rule_hits} == {"公开的秋季赛", "结束的赛事"}


# --- teams and members ----------------------------------------------------------------


@pytest.mark.django_db
def test_teams_exclude_disbanded_ones():
    captain = person("队长搜")
    other = person("队长散")
    team_services.create_team(user=captain, name="猎空小队", description="找输出")
    gone = team_services.create_team(user=other, name="散伙小队")
    gone.disbanded_at = timezone.now()
    gone.save(update_fields=["disbanded_at"])

    hits = services.search_teams(["小队"]).hits

    assert [hit.title for hit in hits] == ["猎空小队"]
    assert hits[0].url == "/teams/" + str(hits[0].url.split("/")[2]) + "/"
    assert "找输出" in services.search_teams(["输出"]).hits[0].excerpt


@pytest.mark.django_db
def test_members_are_the_people_on_the_members_page():
    shown = person("守望老张")
    hidden = person("守望停用")
    hidden.is_active = False
    hidden.save(update_fields=["is_active"])

    hits = services.search_members(["守望"]).hits

    assert [hit.title for hit in hits] == [shown.nickname]
    assert hits[0].url == "/members/"


@pytest.mark.django_db
def test_each_group_stops_at_the_limit():
    for index in range(services.PER_TYPE_LIMIT + 3):
        person(f"批量成员{index:02d}")

    group = services.search_members(["批量成员"])

    assert len(group.hits) == services.PER_TYPE_LIMIT
    assert group.truncated is True


# --- the page -------------------------------------------------------------------------


@pytest.mark.django_db
def test_the_page_without_a_query_shows_the_form_only(client):
    _tree()
    html = client.get(reverse("search")).content.decode()
    assert 'name="q"' in html
    assert "只搜公开内容" in html


@pytest.mark.django_db
def test_the_page_groups_the_results(client, articles):
    live, _draft = articles
    _tournament("源氏杯")

    html = client.get(reverse("search"), {"q": "源氏"}).content.decode()

    assert "文章" in html and live.title in html
    assert "赛事与内战" in html and "源氏杯" in html
    assert "没有找到" not in html
    for attribute in ("x-data", "x-on:", "x-ref", "@click", "onclick=", "style="):
        assert attribute not in html, attribute


@pytest.mark.django_db
def test_the_page_says_when_nothing_matches(client):
    _tree()
    html = client.get(reverse("search"), {"q": "绝对不存在的词"}).content.decode()
    assert "没有找到" in html


@pytest.mark.django_db
def test_the_page_is_rate_limited_per_ip(client):
    _tree()
    cache.clear()
    headers = {"HTTP_X_FORWARDED_FOR": "203.0.113.9"}
    for _ in range(30):
        assert client.get(reverse("search"), {"q": "x"}, **headers).status_code == 200

    response = client.get(reverse("search"), {"q": "x"}, **headers)

    assert response.status_code == 429
    # Another address is unaffected.
    other = client.get(
        reverse("search"), {"q": "x"}, HTTP_X_FORWARDED_FOR="203.0.113.10"
    )
    assert other.status_code == 200


@pytest.mark.django_db
def test_the_header_carries_the_search_box(client):
    _tree()
    html = client.get("/").content.decode()
    assert 'action="/search/"' in html
    assert 'role="search"' in html
    assert "csrfmiddlewaretoken" not in html  # a GET form, fine for the static page


@pytest.mark.django_db
def test_long_queries_are_truncated_not_refused(client):
    _tree()
    response = client.get(reverse("search"), {"q": "词" * 200})
    assert response.status_code == 200
    assert 'value="' + "词" * 50 + '"' in response.content.decode()
