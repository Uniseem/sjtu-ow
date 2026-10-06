"""217 复核 03 评论：复现脚本（只读业务代码，不改）。

在测试机上跑：
    bash scripts/remote-check.sh run uv run pytest -q -s \
        handoff/rounds/217-second-review/findings/03-repro_comments.py

每条 test 断言的是「问题存在」：绿 = 复现了。
"""

import pytest
from django.urls import reverse
from wagtail.models import PageViewRestriction

from comments import services
from comments.models import Comment
from comments.tests.test_comments import article, reader, site  # noqa: F401
from members.tests.test_members import person

HTMX = {"HTTP_HX_REQUEST": "true"}


def _seed(article):
    author = person("撤稿前的评论者")
    comment = services.create(page=article, author=author, body="撤稿前留下的秘密评论")
    return comment


# --- 03-1 未发布 / 私密文章的评论经点赞、编辑、删除接口整块读出 -------------------


@pytest.mark.django_db
def test_like_on_unpublished_article_leaks_section_and_counts(client, article, reader):
    comment = _seed(article)
    article.unpublish()
    # 对照：加载更多、发表都 404
    client.force_login(reader)
    more = client.get(reverse("comment_more", args=[article.pk]))
    print("more on unpublished:", more.status_code)
    assert more.status_code == 404

    response = client.post(reverse("comment_like", args=[comment.pk]), **HTMX)
    html = response.content.decode()
    comment.refresh_from_db()
    print("like on unpublished:", response.status_code,
          "leaks body:", "撤稿前留下的秘密评论" in html,
          "like_count:", comment.like_count)
    assert response.status_code == 200
    assert "撤稿前留下的秘密评论" in html
    assert comment.like_count == 1


@pytest.mark.django_db
def test_like_on_private_article_leaks_section(client, article, reader):
    comment = _seed(article)
    PageViewRestriction.objects.create(
        page=article, restriction_type=PageViewRestriction.PASSWORD, password="x"
    )
    client.force_login(reader)
    page_response = client.get(article.get_url())
    print("article page for reader:", page_response.status_code,
          "body on page:", "撤稿前留下的秘密评论" in page_response.content.decode())

    response = client.post(reverse("comment_like", args=[comment.pk]), **HTMX)
    html = response.content.decode()
    print("like on private:", response.status_code,
          "leaks body:", "撤稿前留下的秘密评论" in html)
    assert "撤稿前留下的秘密评论" not in page_response.content.decode()
    assert "撤稿前留下的秘密评论" in html


@pytest.mark.django_db
def test_author_edits_comment_on_unpublished_article(client, article):
    comment = _seed(article)
    article.unpublish()
    client.force_login(comment.author)
    response = client.post(
        reverse("comment_edit", args=[comment.pk]), {"body": "撤稿后改的"}, **HTMX
    )
    comment.refresh_from_db()
    print("edit on unpublished:", response.status_code, repr(comment.body))
    assert comment.body == "撤稿后改的"


# --- 03-2 换行在浏览器里算 1 个字、服务端算 2 个 --------------------------------------


@pytest.mark.django_db
def test_crlf_counts_double(client, article, reader):
    client.force_login(reader)
    # 浏览器 textarea maxlength 按 LF 计：490 + 10 = 500，提交时是 CRLF
    typed = "字" * 245 + "\n" * 10 + "字" * 245
    assert len(typed) == 500
    submitted = typed.replace("\n", "\r\n")
    response = client.post(
        reverse("comment_create", args=[article.pk]), {"body": submitted}, **HTMX
    )
    html = response.content.decode()
    print("crlf post:", response.status_code, "refused:", "评论最多 500 字" in html,
          "saved:", Comment.objects.filter(page=article).count())
    assert "评论最多 500 字" in html
    assert not Comment.objects.filter(page=article).exists()


# --- N+1：登录读者看交互版 ------------------------------------------------------------


@pytest.mark.django_db
def test_interactive_section_queries_flat(client, article, reader):
    from django.db import connection
    from django.test.utils import CaptureQueriesContext

    client.force_login(reader)
    url = article.get_url() + "?sort=top"

    def seed(n):
        for index in range(n):
            someone = person(f"楼主{Comment.objects.count()}-{index}")
            top = services.create(page=article, author=someone, body="评论")
            services.create(page=article, author=reader, body="回复", parent=top)
            services.toggle_like(comment=top, user=reader)

    def count():
        client.get(url)
        with CaptureQueriesContext(connection) as captured:
            assert client.get(url).status_code == 200
        return len(captured)

    seed(3)
    few = count()
    seed(7)
    many = count()
    print("interactive live render queries:", few, "->", many)
    assert many <= few
