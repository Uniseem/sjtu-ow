"""Design 5.6: article comments, the base (round 072)."""

import pytest
from django.contrib.auth.models import Group
from django.core.cache import cache
from django.core.management import call_command
from django.urls import reverse

from accounts.models import Feature, FeatureUserRule
from comments import services
from comments.models import MAX_BODY, Comment
from content.models import ArticleCategory, ArticlePage
from content.tests.test_content import _article
from core.models import PrerenderedPage
from members.tests.test_members import person
from moderation.models import ModerationItem


@pytest.fixture
def site(db):
    call_command("init_site", verbosity=0)


@pytest.fixture
def article(site):
    from content.models import ArticleIndexPage

    news = ArticleIndexPage.objects.get(slug="news")
    category = ArticleCategory.objects.get(slug="guide")
    author = person("文章作者")
    return _article(news, category, author, title="评论测试文章", slug="comment-test")


@pytest.fixture
def reader(db):
    return person("读者甲")


@pytest.fixture
def editor(site):
    user = person("内容编辑乙")
    user.groups.add(Group.objects.get(name="内容编辑"))
    return user


@pytest.fixture
def prerender_on(settings, tmp_path):
    settings.PRERENDER_ENABLED = True
    settings.PRERENDER_ROOT = tmp_path


def _comment(article, user, body="一条评论", parent=None):
    return services.create(page=article, author=user, body=body, parent=parent)


# --- posting ---------------------------------------------------------------------


@pytest.mark.django_db
def test_a_reader_posts_a_top_level_comment(article, reader):
    comment = _comment(article, reader, "  好文章  ")

    assert comment.body == "好文章"
    assert comment.is_top_level and comment.visible
    assert list(article.comments.all()) == [comment]


@pytest.mark.django_db
def test_a_reply_to_a_reply_stays_in_the_thread(article, reader):
    other = person("读者乙")
    top = _comment(article, reader, "顶层")
    first = _comment(article, other, "回复顶层", parent=top)
    second = _comment(article, reader, "回复回复", parent=first)

    assert first.parent == top and first.reply_to_user == reader
    assert second.parent == top  # not nested under `first`
    assert second.reply_to_user == other


@pytest.mark.django_db
def test_anonymous_and_gated_users_cannot_post(article, reader):
    from django.contrib.auth.models import AnonymousUser

    with pytest.raises(services.CommentError, match="请先登录"):
        services.create(page=article, author=AnonymousUser(), body="匿名")

    FeatureUserRule.objects.create(
        user=reader, feature=Feature.ARTICLE_COMMENT, allowed=False
    )
    with pytest.raises(services.CommentError, match="暂时无法使用此功能"):
        _comment(article, reader)


@pytest.mark.django_db
def test_a_closed_article_takes_no_comments(article, reader):
    ArticlePage.objects.filter(pk=article.pk).update(comments_enabled=False)
    article.refresh_from_db()

    with pytest.raises(services.CommentError, match="关闭了评论"):
        _comment(article, reader)


@pytest.mark.django_db
@pytest.mark.parametrize("body", ["", "   ", "字" * (MAX_BODY + 1)])
def test_the_body_must_be_one_to_five_hundred_characters(article, reader, body):
    with pytest.raises(services.CommentError, match="评论"):
        _comment(article, reader, body)
    assert not article.comments.exists()


@pytest.mark.django_db
def test_a_parent_from_another_article_or_a_hidden_one_is_refused(
    article, reader, editor
):
    from content.models import ArticleIndexPage

    news = ArticleIndexPage.objects.get(slug="news")
    other_article = _article(
        news, article.category, article.author, title="另一篇", slug="other-article"
    )
    foreign = _comment(other_article, reader, "别处的评论")
    with pytest.raises(services.CommentError, match="不在这篇文章里"):
        _comment(article, reader, "跨文章回复", parent=foreign)

    hidden = _comment(article, reader, "会被隐藏")
    services.hide(comment=hidden, actor=editor)
    with pytest.raises(services.CommentError, match="不能回复"):
        _comment(article, reader, "回复隐藏的", parent=hidden)


# --- moderation ------------------------------------------------------------------


@pytest.mark.django_db
def test_every_comment_is_sent_for_review(
    article, reader, django_capture_on_commit_callbacks, settings
):
    settings.MODERATION_API_KEY = "test-key"
    with django_capture_on_commit_callbacks(execute=True):
        comment = _comment(article, reader, "疑似广告")

    item = ModerationItem.objects.get(target_type="comment", target_id=comment.pk)
    assert item.excerpt == "疑似广告"
    assert item.url.endswith(f"#{comment.anchor}")
    assert item.author == reader
    assert reader.email not in item.excerpt


@pytest.mark.django_db
def test_only_editors_hide_and_readers_never_see_hidden_ones(article, reader, editor):
    comment = _comment(article, reader, "要藏起来")
    with pytest.raises(services.CommentError, match="内容编辑权限"):
        services.hide(comment=comment, actor=reader)

    services.hide(comment=comment, actor=editor)

    assert services.thread(article, viewer=reader)["items"] == []
    shown = services.thread(article, viewer=editor)["items"]
    assert [item["comment"] for item in shown] == [comment]
    services.unhide(comment=comment, actor=editor)
    assert len(services.thread(article, viewer=reader)["items"]) == 1


@pytest.mark.django_db
def test_a_hidden_top_level_with_visible_replies_keeps_a_placeholder(
    article, reader, editor
):
    top = _comment(article, reader, "顶层被藏")
    _comment(article, person("读者丙"), "但回复还在", parent=top)
    services.hide(comment=top, actor=editor)

    items = services.thread(article, viewer=reader)["items"]

    assert len(items) == 1 and items[0]["comment"].is_hidden
    assert [reply.body for reply in items[0]["replies"]] == ["但回复还在"]


@pytest.mark.django_db
def test_the_thread_is_newest_first_pinned_on_top_and_paged(article, reader):
    comments = [_comment(article, reader, f"第 {index} 条") for index in range(25)]
    Comment.objects.filter(pk=comments[3].pk).update(is_pinned=True)

    first = services.thread(article, viewer=None, page_number=1)
    second = services.thread(article, viewer=None, page_number=2)

    assert first["total"] == 25 and first["has_next"] and first["next_number"] == 2
    assert first["items"][0]["comment"].pk == comments[3].pk  # pinned first
    assert first["items"][1]["comment"].pk == comments[24].pk  # then newest
    assert len(first["items"]) == services.PAGE_SIZE
    assert len(second["items"]) == 5 and not second["has_next"]


# --- rendering (design 13.13.3, 13.13.5) ---------------------------------------------


@pytest.mark.django_db
def test_the_static_page_lists_comments_read_only(client, article, reader):
    _comment(article, reader, "静态可见")

    html = client.get(article.get_url()).content.decode()

    assert "静态可见" in html
    assert 'data-slot="article-comments:' in html
    assert "登录后评论" in html
    assert "csrfmiddlewaretoken" not in html
    assert "hx-post" not in html
    assert "退出" not in html


@pytest.mark.django_db
def test_the_prerendered_file_carries_nothing_personal(prerender_on, article, reader):
    from django.conf import settings

    from core import prerender

    _comment(article, reader, "进静态页")
    record = prerender.generate(article.get_url())

    assert record.status == PrerenderedPage.Status.READY
    path = settings.PRERENDER_ROOT / article.get_url().strip("/") / "index.html"
    text = path.read_text(encoding="utf-8")
    assert "进静态页" in text
    assert "csrfmiddlewaretoken" not in text
    assert "退出" not in text


@pytest.mark.django_db
def test_the_fragment_gives_a_signed_in_reader_the_composer(client, article, reader):
    client.force_login(reader)
    url = reverse("state_fragment") + f"?slots=article-comments:{article.pk}"

    fragment = client.get(url).content.decode()

    assert 'id="slot-article-comments"' in fragment
    assert 'hx-swap-oob="true"' in fragment
    assert reverse("comment_create", args=[article.pk]) in fragment
    assert "csrfmiddlewaretoken" in fragment


@pytest.mark.django_db
def test_the_fragment_ignores_unknown_and_unpublished_pages(client, article, reader):
    client.force_login(reader)
    article.unpublish()
    url = (
        reverse("state_fragment")
        + f"?slots=article-comments:{article.pk},article-comments:999999"
    )

    assert client.get(url).content.decode() == ""


@pytest.mark.django_db
def test_a_live_render_for_a_signed_in_reader_is_interactive(client, article, reader):
    client.force_login(reader)

    html = client.get(article.get_url() + "?comments=1").content.decode()

    assert 'data-state-filled="1"' in html
    assert reverse("comment_create", args=[article.pk]) in html


@pytest.mark.django_db
def test_editors_see_hide_buttons_and_hidden_bodies(client, article, reader, editor):
    comment = _comment(article, reader, "编辑能看到")
    services.hide(comment=comment, actor=editor)
    client.force_login(editor)
    url = reverse("state_fragment") + f"?slots=article-comments:{article.pk}"

    fragment = client.get(url).content.decode()

    assert "编辑能看到" in fragment
    assert reverse("comment_unhide", args=[comment.pk]) in fragment


@pytest.mark.django_db
def test_no_alpine_expressions_or_inline_handlers(client, article, reader):
    _comment(article, reader, "检查属性")
    client.force_login(reader)
    for html in (
        client.get(article.get_url()).content.decode(),
        client.get(
            reverse("state_fragment") + f"?slots=article-comments:{article.pk}"
        ).content.decode(),
    ):
        for attribute in (
            "x-data",
            "x-on:",
            "x-ref",
            "@click",
            "onclick=",
            "hx-on",
            "style=",
        ):
            assert attribute not in html, attribute


# --- endpoints ------------------------------------------------------------------------


@pytest.mark.django_db
def test_posting_through_the_endpoint(client, article, reader):
    client.force_login(reader)
    cache.clear()

    response = client.post(
        reverse("comment_create", args=[article.pk]),
        {"body": "通过端点"},
        HTTP_HX_REQUEST="true",
    )

    assert response.status_code == 200
    html = response.content.decode()
    assert "通过端点" in html and 'id="slot-article-comments"' in html
    assert article.comments.filter(body="通过端点").exists()


@pytest.mark.django_db
def test_replying_through_the_endpoint(client, article, reader):
    top = _comment(article, person("读者丁"), "顶层")
    client.force_login(reader)
    cache.clear()

    response = client.post(
        reverse("comment_reply", args=[top.pk]), {"body": "端点回复"}
    )

    assert response.status_code == 302
    reply = article.comments.get(body="端点回复")
    assert reply.parent == top


@pytest.mark.django_db
def test_anonymous_posts_are_sent_to_login(client, article):
    url = reverse("comment_create", args=[article.pk])
    plain = client.post(url, {"body": "x"})
    assert plain.status_code == 302 and "/accounts/login/" in plain["Location"]

    htmx = client.post(url, {"body": "x"}, HTTP_HX_REQUEST="true")
    assert htmx.status_code == 200
    assert htmx["HX-Redirect"] == reverse("account_login")


@pytest.mark.django_db
def test_problems_come_back_in_the_section(client, article, reader):
    client.force_login(reader)
    cache.clear()

    response = client.post(
        reverse("comment_create", args=[article.pk]),
        {"body": " "},
        HTTP_HX_REQUEST="true",
    )

    assert response.status_code == 200
    assert "评论不能为空" in response.content.decode()


@pytest.mark.django_db
def test_the_per_minute_limit(client, article, reader):
    client.force_login(reader)
    cache.clear()
    url = reverse("comment_create", args=[article.pk])
    for index in range(3):
        client.post(url, {"body": f"第 {index} 条"}, HTTP_HX_REQUEST="true")

    response = client.post(url, {"body": "第四条"}, HTTP_HX_REQUEST="true")

    assert "评论太频繁" in response.content.decode()
    assert article.comments.count() == 3


@pytest.mark.django_db
def test_unpublished_articles_take_nothing(client, article, reader):
    article.unpublish()
    client.force_login(reader)
    assert (
        client.post(
            reverse("comment_create", args=[article.pk]), {"body": "x"}
        ).status_code
        == 404
    )


@pytest.mark.django_db
def test_load_more_returns_the_next_page(client, article, reader):
    for index in range(22):
        _comment(article, reader, f"评论 {index:02d}")

    response = client.get(reverse("comment_more", args=[article.pk]), {"page": 2})

    html = response.content.decode()
    assert response.status_code == 200
    assert "评论 01" in html and "评论 00" in html  # the two oldest are on page 2
    assert "评论 21" not in html
    assert 'id="comments-more"' in html and "加载更多" not in html


@pytest.mark.django_db
def test_hiding_through_the_endpoint_needs_the_permission(
    client, article, reader, editor
):
    comment = _comment(article, reader, "谁能藏")
    client.force_login(reader)
    assert client.post(reverse("comment_hide", args=[comment.pk])).status_code == 403

    client.force_login(editor)
    response = client.post(
        reverse("comment_hide", args=[comment.pk]), HTTP_HX_REQUEST="true"
    )
    assert response.status_code == 200
    comment.refresh_from_db()
    assert comment.is_hidden


# --- regeneration and nicknames -------------------------------------------------------


@pytest.mark.django_db
def test_posting_and_hiding_regenerate_the_article(
    prerender_on, article, reader, editor, django_capture_on_commit_callbacks
):
    PrerenderedPage.objects.all().delete()
    with django_capture_on_commit_callbacks(execute=True):
        comment = _comment(article, reader, "触发生成")
    assert PrerenderedPage.objects.filter(path=article.get_url()).exists()

    PrerenderedPage.objects.all().delete()
    with django_capture_on_commit_callbacks(execute=True):
        services.hide(comment=comment, actor=editor)
    assert PrerenderedPage.objects.filter(path=article.get_url()).exists()


@pytest.mark.django_db
def test_a_nickname_change_refreshes_commented_articles(prerender_on, article, reader):
    from accounts.services import refresh_nickname_pages

    _comment(article, reader, "改昵称后要刷新")
    PrerenderedPage.objects.all().delete()

    refresh_nickname_pages(reader)

    assert PrerenderedPage.objects.filter(path=article.get_url()).exists()


# --- admin ----------------------------------------------------------------------------


@pytest.mark.django_db
def test_content_editors_open_the_admin_list_and_others_do_not(
    client, article, reader, editor
):
    _comment(article, reader, "后台列表")
    client.force_login(editor)
    assert client.get(reverse("comments:index")).status_code == 200

    manager = person("赛事管理员己")
    manager.groups.add(Group.objects.get(name="赛事管理员"))
    client.force_login(manager)
    response = client.get(reverse("comments:index"))
    assert response.status_code == 302


@pytest.mark.django_db
def test_the_comments_slug_is_reserved():
    from content.models import RESERVED_CHILD_SLUGS

    assert "comments" in RESERVED_CHILD_SLUGS
