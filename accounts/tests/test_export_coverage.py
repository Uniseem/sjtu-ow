"""Round 172: 「导出个人信息」 holds everything about the person (design 3.8).

Comments (072), likes (073) and feature rules had been left out. The first
test lists every column that points at a person, so the next table added
cannot be forgotten: it must go in accounts.services.EXPORTED or NOT_EXPORTED.
"""

import pytest
from django.apps import apps
from django.conf import settings
from django.core.management import call_command

from accounts import services

PROJECT = (
    "accounts.",
    "comments.",
    "content.",
    "core.",
    "members.",
    "moderation.",
    "scrims.",
    "teams.",
    "tournaments.",
)


def _columns_pointing_at_people():
    person = apps.get_model(settings.AUTH_USER_MODEL)
    found = set()
    for model in apps.get_models():
        if not model.__module__.startswith(PROJECT):
            continue
        for field in model._meta.get_fields():
            if (
                getattr(field, "related_model", None) is person
                and field.concrete
                and (field.many_to_one or field.one_to_one or field.many_to_many)
            ):
                found.add(f"{model._meta.label}.{field.name}")
    return found


@pytest.mark.django_db
def test_every_column_pointing_at_a_person_is_accounted_for():
    from core.tests.test_chapter15_audit import make_user

    assert not set(services.EXPORTED) & set(services.NOT_EXPORTED)
    assert _columns_pointing_at_people() == set(services.EXPORTED) | set(
        services.NOT_EXPORTED
    )
    sections = services.personal_data(make_user(1)).keys()
    assert set(services.EXPORTED.values()) <= set(sections)


@pytest.mark.django_db
def test_comments_likes_and_rules_go_out(client):
    from accounts.models import FeatureUserRule
    from accounts.permissions import Feature
    from comments.models import Comment, CommentLike
    from core.tests.test_chapter15_audit import _publish_article, _verified, make_user

    call_command("init_site", verbosity=0)
    me, other = _verified(make_user(1)), _verified(make_user(2))
    article = _publish_article(other)
    Comment.objects.create(page=article, author=me, body="我的评论")
    Comment.objects.create(page=article, author=me, body="", is_deleted=True)
    Comment.objects.create(page=article, author=me, body="被藏起来的", is_hidden=True)
    theirs = Comment.objects.create(page=article, author=other, body="别人的评论")
    CommentLike.objects.create(comment=theirs, user=me)
    FeatureUserRule.objects.create(
        user=me, feature=Feature.ARTICLE_COMMENT, allowed=False, note="刷屏"
    )

    data = services.personal_data(me)
    assert [(row["body"], row["state"]) for row in data["comments"]] == [
        ("我的评论", "公开"),
        ("", "作者已删除"),
        ("被藏起来的", "已隐藏"),
    ]
    assert all(row["article"] == article.title for row in data["comments"])
    assert data["comment_likes"] == [
        {"article": article.title, "liked_at": data["comment_likes"][0]["liked_at"]}
    ]
    assert data["feature_rules"][0]["reason"] == "刷屏"
    assert data["feature_rules"][0]["allowed"] is False
    assert "别人的评论" not in str(data)
