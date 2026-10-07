"""A comment number alone must not open a section (218, 217 review 03-1).

Like, edit, delete, pin, unpin, hide, unhide and reply took the comment by its
number and rendered the article's whole comment section back, without asking
whether the article is live and public. With the HTMX header that was the first
page of comments of a taken-down or password-protected article, for any member.
"""

import pytest
from django.contrib.auth.models import Group
from django.urls import reverse
from wagtail.models import PageViewRestriction

from comments import services
from comments.tests.test_comment_extras import _make_article
from comments.tests.test_comments import _comment
from members.tests.test_members import person

SECRET = "只该在文章页里看到的评论正文"

# endpoint -> who calls it ("author" wrote the comment, "editor" moderates,
# "other" is any other member)
ENDPOINTS = {
    "comment_like": "other",
    "comment_reply": "other",
    "comment_edit": "author",
    "comment_delete": "author",
    "comment_pin": "editor",
    "comment_unpin": "editor",
    "comment_hide": "editor",
    "comment_unhide": "editor",
}


def _hide_article(article, how):
    if how == "unpublished":
        article.unpublish()
    elif how == "password":
        PageViewRestriction.objects.create(
            page=article,
            restriction_type=PageViewRestriction.PASSWORD,
            password="hunter2",
        )
    elif how == "login":
        PageViewRestriction.objects.create(
            page=article, restriction_type=PageViewRestriction.LOGIN
        )


@pytest.fixture
def world(db):
    article = _make_article()
    author = person("评论作者")
    other = person("路过的成员")
    editor = person("内容编辑丙")
    editor.groups.add(Group.objects.get(name="内容编辑"))
    comment = _comment(article, author, SECRET)
    return {
        "article": article,
        "comment": comment,
        "author": author,
        "other": other,
        "editor": editor,
    }


@pytest.mark.django_db
@pytest.mark.parametrize("how", ["unpublished", "password", "login"])
@pytest.mark.parametrize("name", ENDPOINTS)
def test_no_endpoint_answers_for_an_article_that_is_not_public(
    client, world, name, how
):
    comment = world["comment"]
    _hide_article(world["article"], how)
    client.force_login(world[ENDPOINTS[name]])

    response = client.post(
        reverse(name, args=[comment.pk]),
        {"body": "改过的正文"},
        HTTP_HX_REQUEST="true",
    )

    assert response.status_code == 404
    assert SECRET not in response.content.decode()
    comment.refresh_from_db()
    assert comment.body == SECRET
    assert comment.like_count == 0
    assert not (comment.is_pinned or comment.is_hidden or comment.is_deleted)
    assert comment.replies.count() == 0


@pytest.mark.django_db
@pytest.mark.parametrize("name", ["comment_like", "comment_edit"])
def test_the_too_often_answer_does_not_open_the_section_either(
    client, world, monkeypatch, name
):
    """Like and edit have a second branch for a member who is over the limit;
    it rendered the section before looking at the article."""
    monkeypatch.setattr("comments.views.over_limit", lambda *args, **kwargs: True)
    world["article"].unpublish()
    client.force_login(world[ENDPOINTS[name]])

    response = client.post(
        reverse(name, args=[world["comment"].pk]), HTTP_HX_REQUEST="true"
    )

    assert response.status_code == 404
    assert SECRET not in response.content.decode()


@pytest.mark.django_db
def test_a_live_public_article_still_answers(client, world):
    """The control: the same call on a published article works, so the 404s
    above come from the article's state and nothing else."""
    client.force_login(world["other"])
    response = client.post(
        reverse("comment_like", args=[world["comment"].pk]), HTTP_HX_REQUEST="true"
    )
    assert response.status_code == 200
    assert SECRET in response.content.decode()
    assert services.commentable_page(world["article"].pk) is not None
