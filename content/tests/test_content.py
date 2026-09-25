from io import BytesIO

import pytest
from django.contrib.auth.models import Group
from django.core.exceptions import ValidationError
from django.core.files.base import ContentFile
from django.core.management import call_command
from django.utils import timezone
from PIL import Image as PILImage
from wagtail.embeds.oembed_providers import all_providers
from wagtail.images.models import Image
from wagtail.models import Collection, Site

from accounts.models import User
from content.models import (
    MAX_PINNED_ARTICLES,
    ArticleCategory,
    ArticleIndexPage,
    ArticlePage,
    HomePage,
    HomePagePinnedArticle,
    StandardPage,
)
from content.services import INITIAL_CATEGORIES, WAGTAIL_STOCK_GROUP_NAMES
from core.models import SiteSettings

VALID_PASSWORD = "Correct-Horse-Battery-1"


def _user(email="editor@example.com", nickname="编辑同学"):
    return User.objects.create_user(
        email=email,
        password=VALID_PASSWORD,
        nickname=nickname,
        agreed_terms_at=timezone.now(),
        agreed_cross_border_at=timezone.now(),
    )


def _image(title="cover"):
    collection = Collection.get_first_root_node()
    if collection is None:
        collection = Collection.add_root(name="Root")
    buffer = BytesIO()
    PILImage.new("RGB", (1200, 630), color=(12, 48, 96)).save(buffer, format="PNG")
    image = Image(
        title=title,
        width=1200,
        height=630,
        collection=collection,
        file=ContentFile(buffer.getvalue(), name=f"{title}.png"),
    )
    image.save()
    return image


def _tree():
    call_command("init_site", verbosity=0)
    home = HomePage.objects.get()
    news = ArticleIndexPage.objects.get(slug="news")
    return home, news


def _article(parent, category, author, *, title, slug, live=True, **fields):
    fields.setdefault("summary", "这是摘要")
    fields.setdefault("body", [("paragraph", "<p>这是正文</p>")])
    page = ArticlePage(
        title=title,
        slug=slug,
        category=category,
        author=author,
        owner=author,
        **fields,
    )
    parent.add_child(instance=page)
    if live:
        page.save_revision().publish()
    else:
        page.unpublish()
    return ArticlePage.objects.get(pk=page.pk)


@pytest.mark.django_db
def test_bilibili_is_not_a_builtin_oembed_provider():
    blob = repr(all_providers).lower()
    assert "bilibili" not in blob
    assert "b23.tv" not in blob


@pytest.mark.django_db
def test_init_site_creates_categories_and_page_tree_idempotently():
    Group.objects.get_or_create(name="Editors")
    Group.objects.get_or_create(name="Moderators")
    call_command("init_site", verbosity=0)
    call_command("init_site", verbosity=0)

    slugs = list(
        ArticleCategory.objects.order_by("sort_order").values_list("slug", flat=True)
    )
    assert slugs[:5] == [item[0] for item in INITIAL_CATEGORIES]
    notice = ArticleCategory.objects.get(slug="notice")
    guide = ArticleCategory.objects.get(slug="guide")
    assert notice.allow_submission is False
    assert notice.name == "公告"
    assert guide.allow_submission is True

    assert HomePage.objects.filter(depth=2, live=True).count() == 1
    home = HomePage.objects.get()
    site = Site.objects.get(is_default_site=True)
    assert site.root_page_id == home.id
    assert ArticleIndexPage.objects.filter(slug="news", live=True).count() == 1
    for slug in ("terms", "privacy", "about"):
        assert StandardPage.objects.filter(slug=slug, live=True).count() == 1
    assert not Group.objects.filter(name__in=WAGTAIL_STOCK_GROUP_NAMES).exists()


@pytest.mark.django_db
def test_article_list_pagination_and_category_filter(client):
    home, news = _tree()
    author = _user()
    guide = ArticleCategory.objects.get(slug="guide")
    notice = ArticleCategory.objects.get(slug="notice")
    for index in range(13):
        _article(
            news,
            guide if index < 12 else notice,
            author,
            title=f"攻略 {index}",
            slug=f"guide-{index}",
        )

    listing = client.get("/news/")
    assert listing.status_code == 200
    html = listing.content.decode("utf-8")
    assert "1 / 2" in html
    assert "下一页" in html

    page_two = client.get("/news/?page=2")
    assert page_two.status_code == 200
    html_two = page_two.content.decode("utf-8")
    assert "2 / 2" in html_two
    assert "上一页" in html_two

    filtered = client.get("/news/?category=notice")
    assert filtered.status_code == 200
    filtered_html = filtered.content.decode("utf-8")
    assert "攻略 12" in filtered_html
    assert "攻略 0" not in filtered_html
    assert "category=notice" in filtered_html or "btn-primary" in filtered_html


@pytest.mark.django_db
def test_article_detail_visible_and_unpublished_is_404(client):
    _home, news = _tree()
    author = _user()
    guide = ArticleCategory.objects.get(slug="guide")
    article = _article(
        news,
        guide,
        author,
        title="公开攻略",
        slug="public-guide",
        summary="列表摘要",
        body=[
            ("paragraph", "<p>正文段落</p>"),
            ("quote", {"text": "一句引用", "attribution": "出处"}),
        ],
    )
    url = article.url
    response = client.get(url)
    assert response.status_code == 200
    html = response.content.decode("utf-8")
    assert "公开攻略" in html
    assert "编辑同学" in html
    assert "攻略" in html
    assert "正文段落" in html
    assert "一句引用" in html
    assert "列表摘要" in html
    assert 'style="' not in html

    article.unpublish()
    hidden = client.get(url)
    assert hidden.status_code == 404


@pytest.mark.django_db
def test_pinned_articles_max_three():
    home, news = _tree()
    author = _user()
    guide = ArticleCategory.objects.get(slug="guide")
    articles = [
        _article(news, guide, author, title=f"置顶 {i}", slug=f"pin-{i}")
        for i in range(4)
    ]
    for index, article in enumerate(articles[:MAX_PINNED_ARTICLES]):
        HomePagePinnedArticle.objects.create(
            page=home, article=article, sort_order=index
        )
    home.full_clean()
    extra = HomePagePinnedArticle(page=home, article=articles[3], sort_order=3)
    with pytest.raises(ValidationError, match="最多 3 篇"):
        extra.full_clean()
    with pytest.raises(ValidationError, match="最多 3 篇"):
        extra.save()
    assert home.pinned_articles.count() == MAX_PINNED_ARTICLES


@pytest.mark.django_db
def test_home_uses_pinned_articles_when_present(client):
    home, news = _tree()
    author = _user()
    guide = ArticleCategory.objects.get(slug="guide")
    pinned = _article(news, guide, author, title="置顶一篇", slug="pinned")
    latest = _article(news, guide, author, title="最新一篇", slug="latest")
    HomePagePinnedArticle.objects.create(page=home, article=pinned, sort_order=0)
    response = client.get("/")
    html = response.content.decode("utf-8")
    # Round 065 (design 5.2): the older pinned article leads, the latest follows.
    assert html.index("置顶一篇") < html.index("最新一篇")
    # Round 056: the tournament and scrim blocks used to say "即将开放".
    assert "现在没有正在报名的赛事" in html
    assert "未来 7 天没有内战" in html
    assert latest.title == "最新一篇"


@pytest.mark.django_db
def test_reserved_slug_rejected_on_homepage_children():
    page = StandardPage(title="战队占位", slug="teams", body=[])
    with pytest.raises(ValidationError, match="固定路由"):
        page.clean()


@pytest.mark.django_db
def test_page_meta_open_graph_and_canonical(client):
    _home, news = _tree()
    author = _user()
    guide = ArticleCategory.objects.get(slug="guide")
    cover = _image("article-cover")
    article = _article(
        news,
        guide,
        author,
        title="带封面的文章",
        slug="with-cover",
        summary="摘要用于描述",
        cover=cover,
    )
    article.seo_title = "SEO 标题"
    article.search_description = "SEO 描述"
    article.save()
    article.save_revision().publish()

    settings_obj = SiteSettings.load()
    settings_obj.site_description = "站点简介文案"
    settings_obj.save()

    response = client.get(article.url)
    html = response.content.decode("utf-8")
    assert "<title>SEO 标题 · 上海交通大学守望先锋社区</title>" in html
    assert 'name="description" content="SEO 描述"' in html
    assert 'rel="canonical"' in html
    assert article.url in html
    assert 'property="og:title" content="SEO 标题"' in html
    assert 'property="og:description" content="SEO 描述"' in html
    assert 'property="og:image"' in html
    assert 'property="og:url"' in html

    terms = client.get("/terms/")
    terms_html = terms.content.decode("utf-8")
    assert 'name="description" content="站点简介文案"' in terms_html
    assert 'property="og:title" content="用户协议"' in terms_html


@pytest.mark.django_db
def test_sitemap_lists_only_live_articles_and_standard_pages(client):
    _home, news = _tree()
    author = _user()
    guide = ArticleCategory.objects.get(slug="guide")
    live = _article(news, guide, author, title="活着", slug="live-one")
    dead = _article(news, guide, author, title="草稿", slug="dead-one", live=False)

    response = client.get("/sitemap.xml")
    assert response.status_code == 200
    body = response.content.decode("utf-8")
    assert live.url.rstrip("/") in body
    assert dead.slug not in body
    assert "/terms/" in body
    assert "/privacy/" in body
    assert "/news/</loc>" not in body
    assert "<urlset" in body


@pytest.mark.django_db
def test_robots_disallows_private_paths(client):
    response = client.get("/robots.txt")
    assert response.status_code == 200
    body = response.content.decode("utf-8")
    for path in ("/admin/", "/me/", "/accounts/", "/_fragments/", "/search/"):
        assert f"Disallow: {path}" in body
    assert "Sitemap:" in body


@pytest.mark.django_db
def test_standard_pages_render(client):
    _tree()
    for path in ("/terms/", "/privacy/", "/about/"):
        response = client.get(path)
        assert response.status_code == 200
        html = response.content.decode("utf-8")
        assert 'style="' not in html


@pytest.mark.django_db
def test_homepage_clean_refuses_a_fourth_pin_before_any_are_saved():
    """The editor submits all pins at once; none exist in the database yet."""
    home, news = _tree()
    author = _user()
    guide = ArticleCategory.objects.get(slug="guide")
    home.pinned_articles = [
        HomePagePinnedArticle(
            article=_article(news, guide, author, title=f"待置顶 {i}", slug=f"new-{i}"),
            sort_order=i,
        )
        for i in range(MAX_PINNED_ARTICLES + 1)
    ]
    with pytest.raises(ValidationError, match="最多 3 篇"):
        home.clean()


@pytest.mark.django_db
def test_robots_disallows_everything_in_the_test_environment(client, settings):
    """Design 16.10: the test site must stay out of search results."""
    settings.TEST_ENVIRONMENT = True
    response = client.get("/robots.txt")
    assert response.status_code == 200
    assert response.content.decode("utf-8") == "User-agent: *\nDisallow: /\n"
