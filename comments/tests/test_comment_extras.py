"""Design 5.6 (v1.9.1): likes, sorting, pinning, editing and deleting (round 073)."""

import threading

import pytest
from django.contrib.auth.models import Group
from django.core.cache import cache
from django.core.management import call_command
from django.db import IntegrityError, connections
from django.urls import reverse

from comments import services
from comments.models import Comment, CommentLike
from comments.tests.test_comments import _comment
from content.models import ArticleCategory
from content.tests.test_content import _article
from core.models import PrerenderedPage
from members.tests.test_members import person
from moderation.models import ModerationItem


def _make_article():
    from content.models import ArticleIndexPage

    call_command("init_site", verbosity=0)
    news = ArticleIndexPage.objects.get(slug="news")
    category = ArticleCategory.objects.get(slug="guide")
    return _article(news, category, person("文章作者"), title="增强测试", slug="extras")


@pytest.fixture
def article(db):
    return _make_article()


@pytest.fixture
def reader(db):
    return person("读者甲")


@pytest.fixture
def editor(db):
    user = person("内容编辑乙")
    user.groups.add(Group.objects.get(name="内容编辑"))
    return user


@pytest.fixture
def prerender_on(settings, tmp_path):
    settings.PRERENDER_ENABLED = True
    settings.PRERENDER_ROOT = tmp_path


def _order(article, **kwargs):
    return [
        item["comment"].body for item in services.thread(article, **kwargs)["items"]
    ]


# --- likes ---------------------------------------------------------------------------


@pytest.mark.django_db
def test_liking_twice_takes_it_back(article, reader):
    comment = _comment(article, person("被赞的人"), "赞我")

    assert services.toggle_like(comment=comment, user=reader) is True
    assert comment.like_count == 1
    assert services.toggle_like(comment=comment, user=reader) is False
    assert comment.like_count == 0
    assert not CommentLike.objects.exists()


@pytest.mark.django_db
def test_one_like_per_person_is_enforced_by_the_database(article, reader):
    comment = _comment(article, reader, "唯一")
    CommentLike.objects.create(comment=comment, user=reader)
    with pytest.raises(IntegrityError):
        CommentLike.objects.create(comment=comment, user=reader)


@pytest.mark.django_db(transaction=True)
def test_a_double_click_leaves_at_most_one_like():
    """Two simultaneous likes from one person (design 12.11): one row, count 1."""
    article = _make_article()
    reader = person("手快的人")
    comment = _comment(article, person("被赞的人"), "并发")
    start = threading.Barrier(2)
    outcomes = [None, None]

    def press(index):
        def inner():
            start.wait()
            try:
                outcomes[index] = (
                    "ok",
                    services.toggle_like(comment=comment, user=reader),
                )
            except Exception as exc:  # noqa: BLE001 — the exception is the result
                outcomes[index] = ("error", exc)
            finally:
                connections.close_all()

        return inner

    threads = [threading.Thread(target=press(index)) for index in range(2)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join(timeout=30)

    assert all(not thread.is_alive() for thread in threads), "有线程卡住了"
    assert CommentLike.objects.filter(comment=comment).count() <= 1
    comment.refresh_from_db()
    assert comment.like_count == CommentLike.objects.filter(comment=comment).count()
    assert all(outcome is not None and outcome[0] == "ok" for outcome in outcomes)


@pytest.mark.django_db
def test_hidden_and_deleted_comments_take_no_likes(article, reader, editor):
    hidden = _comment(article, reader, "藏")
    services.hide(comment=hidden, actor=editor)
    with pytest.raises(services.CommentError, match="不能点赞"):
        services.toggle_like(comment=hidden, user=reader)

    gone = _comment(article, reader, "删")
    services.delete(comment=gone, actor=reader)
    with pytest.raises(services.CommentError, match="不能点赞"):
        services.toggle_like(comment=gone, user=reader)


@pytest.mark.django_db
def test_anonymous_visitors_cannot_like(article, reader):
    from django.contrib.auth.models import AnonymousUser

    comment = _comment(article, reader, "匿名")
    with pytest.raises(services.CommentError, match="请先登录"):
        services.toggle_like(comment=comment, user=AnonymousUser())


@pytest.mark.django_db
def test_the_viewer_sees_which_comments_they_liked(article, reader):
    mine = _comment(article, reader, "我赞了")
    other = _comment(article, reader, "没赞")
    services.toggle_like(comment=mine, user=reader)

    data = services.thread(article, viewer=reader)

    assert data["liked"] == {mine.pk}
    assert other.pk not in data["liked"]


# --- sorting and pinning ------------------------------------------------------------


@pytest.mark.django_db
def test_top_sorts_by_likes_then_replies_then_time(article, reader):
    liked = _comment(article, reader, "有赞")  # oldest
    replied = _comment(article, reader, "有回复")
    _comment(article, person("回复者"), "回一句", parent=replied)
    _comment(article, reader, "安静")  # newest
    services.toggle_like(comment=liked, user=person("点赞者"))

    assert _order(article, sort="top") == ["有赞", "有回复", "安静"]
    assert _order(article, sort="new") == ["安静", "有回复", "有赞"]
    assert _order(article, sort="nonsense") == ["安静", "有回复", "有赞"]
    assert services.thread(article, sort="nonsense")["sort"] == "new"


@pytest.mark.django_db
def test_hidden_replies_do_not_count_towards_heat(article, reader, editor):
    noisy = _comment(article, reader, "回复被藏了")  # older
    reply = _comment(article, person("回复者"), "被藏", parent=noisy)
    _comment(article, reader, "没回复")  # newer
    services.hide(comment=reply, actor=editor)

    # Equal heat once the hidden reply is discounted, so the newer one leads.
    assert _order(article, sort="top") == ["没回复", "回复被藏了"]
    heat = {
        item["comment"].body: item["comment"].reply_count
        for item in services.thread(article, sort="top")["items"]
    }
    assert heat == {"没回复": 0, "回复被藏了": 0}


@pytest.mark.django_db
def test_pinning_replaces_the_previous_pin_and_leads_every_sort(
    article, reader, editor
):
    first = _comment(article, reader, "先置顶")
    second = _comment(article, reader, "后置顶")
    _comment(article, reader, "最新的")
    services.pin(comment=first, actor=editor)
    services.pin(comment=second, actor=editor)

    first.refresh_from_db()
    assert not first.is_pinned
    assert Comment.objects.filter(is_pinned=True).count() == 1
    for sort in ("new", "top"):
        assert _order(article, sort=sort)[0] == "后置顶", sort

    services.unpin(comment=second, actor=editor)
    second.refresh_from_db()
    assert not second.is_pinned


@pytest.mark.django_db
def test_the_database_allows_one_pin_per_article(article, reader):
    Comment.objects.filter(pk=_comment(article, reader, "一").pk).update(is_pinned=True)
    with pytest.raises(IntegrityError):
        Comment.objects.filter(pk=_comment(article, reader, "二").pk).update(
            is_pinned=True
        )


@pytest.mark.django_db
def test_only_editors_pin_and_only_visible_top_level_comments(article, reader, editor):
    top = _comment(article, reader, "顶层")
    reply = _comment(article, reader, "回复", parent=top)
    with pytest.raises(services.CommentError, match="内容编辑权限"):
        services.pin(comment=top, actor=reader)
    with pytest.raises(services.CommentError, match="只能置顶顶层"):
        services.pin(comment=reply, actor=editor)

    hidden = _comment(article, reader, "藏起来的")
    services.hide(comment=hidden, actor=editor)
    with pytest.raises(services.CommentError, match="不能置顶"):
        services.pin(comment=hidden, actor=editor)


@pytest.mark.django_db
def test_hiding_or_deleting_a_pinned_comment_unpins_it(article, reader, editor):
    pinned = _comment(article, reader, "置顶后隐藏")
    services.pin(comment=pinned, actor=editor)
    services.hide(comment=pinned, actor=editor)
    pinned.refresh_from_db()
    assert not pinned.is_pinned

    again = _comment(article, reader, "置顶后删除")
    services.pin(comment=again, actor=editor)
    services.delete(comment=again, actor=reader)
    again.refresh_from_db()
    assert not again.is_pinned


# --- editing and deleting -----------------------------------------------------------


@pytest.mark.django_db
def test_the_author_edits_and_it_is_reviewed_again(
    article, reader, settings, django_capture_on_commit_callbacks
):
    settings.MODERATION_API_KEY = "test-key"
    with django_capture_on_commit_callbacks(execute=True):
        comment = _comment(article, reader, "第一版")
    services.toggle_like(comment=comment, user=person("点赞者"))

    with django_capture_on_commit_callbacks(execute=True):
        services.edit(comment=comment, actor=reader, body="  第二版  ")

    comment.refresh_from_db()
    assert comment.body == "第二版"
    assert comment.edited_at is not None
    assert comment.like_count == 1
    items = ModerationItem.objects.filter(target_type="comment", target_id=comment.pk)
    assert items.count() == 2
    assert items.filter(excerpt="第二版").exists()


@pytest.mark.django_db
@pytest.mark.parametrize("body", ["", "   ", "字" * 501])
def test_edits_obey_the_length_rules(article, reader, body):
    comment = _comment(article, reader, "原文")
    with pytest.raises(services.CommentError, match="评论"):
        services.edit(comment=comment, actor=reader, body=body)
    comment.refresh_from_db()
    assert comment.body == "原文" and comment.edited_at is None


@pytest.mark.django_db
def test_hidden_comments_cannot_be_edited(article, reader, editor):
    comment = _comment(article, reader, "被藏的")
    services.hide(comment=comment, actor=editor)
    with pytest.raises(services.CommentError, match="不能编辑"):
        services.edit(comment=comment, actor=reader, body="想改回来")


@pytest.mark.django_db
def test_strangers_cannot_edit_or_delete(article, reader):
    comment = _comment(article, reader, "别人的")
    stranger = person("路人")
    with pytest.raises(services.CommentError, match="自己的评论"):
        services.edit(comment=comment, actor=stranger, body="改")
    with pytest.raises(services.CommentError, match="自己的评论"):
        services.delete(comment=comment, actor=stranger)
    comment.refresh_from_db()
    assert comment.body == "别人的" and not comment.is_deleted


@pytest.mark.django_db
def test_deleting_keeps_the_thread_and_blocks_replies_and_likes(article, reader):
    top = _comment(article, reader, "要删的顶层")
    reply = _comment(article, person("回复者"), "留下的回复", parent=top)

    services.delete(comment=top, actor=reader)

    top.refresh_from_db()
    assert top.is_deleted and top.body == ""
    items = services.thread(article)["items"]
    assert [item["comment"].pk for item in items] == [top.pk]
    assert [r.pk for r in items[0]["replies"]] == [reply.pk]
    with pytest.raises(services.CommentError, match="不能回复"):
        _comment(article, reader, "回复已删的", parent=top)

    lonely = _comment(article, reader, "没有回复的")
    services.delete(comment=lonely, actor=reader)
    assert "没有回复的" not in _order(article)
    assert lonely.pk not in [
        item["comment"].pk for item in services.thread(article)["items"]
    ]


@pytest.mark.django_db
def test_a_deleted_reply_disappears_from_the_thread(article, reader):
    top = _comment(article, reader, "顶层")
    reply = _comment(article, reader, "要删的回复", parent=top)
    services.delete(comment=reply, actor=reader)

    items = services.thread(article)["items"]
    assert items[0]["replies"] == []


# --- the page and the endpoints ---


@pytest.mark.django_db
def test_the_static_page_shows_counts_placeholders_and_sort_links(
    client, article, reader
):
    top = _comment(article, reader, "有赞的")
    _comment(article, reader, "第二条")
    services.toggle_like(comment=top, user=person("点赞者"))
    deleted = _comment(article, reader, "删掉的顶层")
    _comment(article, person("回复者"), "还在的回复", parent=deleted)
    services.delete(comment=deleted, actor=reader)

    html = client.get(article.get_url()).content.decode()

    assert "data-like-count>1<" in html
    assert "评论已删除" in html and "还在的回复" in html
    assert "?sort=top#comments" in html
    assert "hx-post" not in html and "csrfmiddlewaretoken" not in html
    assert 'id="comment-sort"' not in html
    assert html.index("第二条") < html.index("有赞的")
    hottest = client.get(article.get_url() + "?sort=top").content.decode()
    assert hottest.index("有赞的") < hottest.index("第二条")


@pytest.mark.django_db
def test_like_edit_delete_pin_through_the_endpoints(client, article, reader, editor):
    comment = _comment(article, reader, "端点")
    client.force_login(reader)
    cache.clear()

    liked = client.post(
        reverse("comment_like", args=[comment.pk]), HTTP_HX_REQUEST="true"
    )
    assert liked.status_code == 200
    assert "已赞" in liked.content.decode()
    comment.refresh_from_db()
    assert comment.like_count == 1

    edited = client.post(
        reverse("comment_edit", args=[comment.pk]),
        {"body": "端点改过"},
        HTTP_HX_REQUEST="true",
    )
    assert "端点改过" in edited.content.decode()
    assert "已编辑" in edited.content.decode()

    client.force_login(editor)
    pinned = client.post(
        reverse("comment_pin", args=[comment.pk]), HTTP_HX_REQUEST="true"
    )
    assert "取消置顶" in pinned.content.decode()
    comment.refresh_from_db()
    assert comment.is_pinned
    unpinned = client.post(
        reverse("comment_unpin", args=[comment.pk]), HTTP_HX_REQUEST="true"
    )
    assert "取消置顶" not in unpinned.content.decode()

    client.force_login(reader)
    gone = client.post(
        reverse("comment_delete", args=[comment.pk]), HTTP_HX_REQUEST="true"
    )
    assert gone.status_code == 200
    comment.refresh_from_db()
    assert comment.is_deleted


@pytest.mark.django_db
def test_htmx_actions_keep_the_visitors_sort(client, article, reader):
    old = _comment(article, reader, "老的有赞")
    _comment(article, reader, "新的没赞")
    services.toggle_like(comment=old, user=person("点赞者"))
    client.force_login(reader)
    cache.clear()

    response = client.post(
        reverse("comment_like", args=[old.pk]), {"sort": "top"}, HTTP_HX_REQUEST="true"
    )

    html = response.content.decode()
    assert html.index("老的有赞") < html.index("新的没赞")
    assert 'id="comment-sort" name="sort" value="top"' in html
    assert 'hx-include="#comment-sort"' in html


@pytest.mark.django_db
def test_the_endpoints_refuse_strangers_and_anonymous_visitors(client, article, reader):
    comment = _comment(article, reader, "别人的")
    anonymous = client.post(
        reverse("comment_like", args=[comment.pk]), HTTP_HX_REQUEST="true"
    )
    assert anonymous["HX-Redirect"] == reverse("account_login")

    client.force_login(person("路人"))
    response = client.post(
        reverse("comment_delete", args=[comment.pk]), HTTP_HX_REQUEST="true"
    )
    assert "自己的评论" in response.content.decode()
    comment.refresh_from_db()
    assert not comment.is_deleted

    pin = client.post(reverse("comment_pin", args=[comment.pk]), HTTP_HX_REQUEST="true")
    assert "内容编辑权限" in pin.content.decode()
    comment.refresh_from_db()
    assert not comment.is_pinned


@pytest.mark.django_db
def test_likes_are_rate_limited(client, article, reader):
    comment = _comment(article, reader, "限流")
    client.force_login(reader)
    cache.clear()
    url = reverse("comment_like", args=[comment.pk])
    for _ in range(60):
        client.post(url, HTTP_HX_REQUEST="true")

    response = client.post(url, HTTP_HX_REQUEST="true")

    assert "点赞太频繁" in response.content.decode()
    assert CommentLike.objects.filter(comment=comment).count() == 0  # 60 toggles


@pytest.mark.django_db
def test_load_more_keeps_the_sort(client, article, reader):
    for index in range(21):
        _comment(article, reader, f"热度 {index:02d}")
    hot = Comment.objects.get(body="热度 00")  # the oldest: last under 「最新」
    services.toggle_like(comment=hot, user=person("点赞者"))

    newest = client.get(reverse("comment_more", args=[article.pk]), {"page": 2})
    hottest = client.get(
        reverse("comment_more", args=[article.pk]), {"page": 2, "sort": "top"}
    )

    assert "热度 00" in newest.content.decode()
    assert "热度 00" not in hottest.content.decode()
    assert "热度 01" in hottest.content.decode()


@pytest.mark.django_db
def test_the_interactive_section_has_no_alpine_or_inline_handlers(
    client, article, reader, editor
):
    mine = _comment(article, reader, "自己的")
    _comment(article, person("别人"), "别人的")
    client.force_login(reader)
    html = client.get(article.get_url() + "?sort=new").content.decode()
    assert "hx-post" in html and 'name="sort"' in html
    for banned in ("x-data", "x-on:", "@click", "onclick=", "hx-on", "style="):
        assert banned not in html, banned
    assert html.count("删除这条评论") == 1  # only my own comment offers 编辑 / 删除
    assert reverse("comment_edit", args=[mine.pk]) in html

    client.force_login(editor)
    html = client.get(article.get_url() + "?sort=new").content.decode()
    assert reverse("comment_pin", args=[mine.pk]) in html


# --- admin ---


@pytest.mark.django_db
def test_the_admin_form_moves_the_pin_and_refuses_replies(
    client, article, reader, editor
):
    first = _comment(article, reader, "先置顶")
    second = _comment(article, reader, "后置顶")
    reply = _comment(article, reader, "回复", parent=first)
    services.pin(comment=first, actor=editor)
    client.force_login(editor)

    moved = client.post(reverse("comments:edit", args=[second.pk]), {"is_pinned": "on"})
    assert moved.status_code == 302
    first.refresh_from_db()
    second.refresh_from_db()
    assert second.is_pinned and not first.is_pinned

    refused = client.post(
        reverse("comments:edit", args=[reply.pk]), {"is_pinned": "on"}
    )
    assert refused.status_code == 200
    assert "只能置顶顶层评论" in refused.content.decode()
    reply.refresh_from_db()
    assert not reply.is_pinned

    both = client.post(
        reverse("comments:edit", args=[second.pk]),
        {"is_pinned": "on", "is_hidden": "on"},
    )
    assert both.status_code == 200
    assert "不能置顶" in both.content.decode()


# --- regeneration ---


@pytest.mark.django_db
def test_every_change_regenerates_the_article(
    prerender_on, article, reader, editor, django_capture_on_commit_callbacks
):
    comment = _comment(article, reader, "会刷新")
    actions = [
        lambda: services.toggle_like(comment=comment, user=reader),
        lambda: services.pin(comment=comment, actor=editor),
        lambda: services.unpin(comment=comment, actor=editor),
        lambda: services.edit(comment=comment, actor=reader, body="改了"),
        lambda: services.delete(comment=comment, actor=reader),
    ]
    for action in actions:
        PrerenderedPage.objects.all().delete()
        with django_capture_on_commit_callbacks(execute=True):
            action()
        assert PrerenderedPage.objects.filter(path=article.get_url()).exists(), action
