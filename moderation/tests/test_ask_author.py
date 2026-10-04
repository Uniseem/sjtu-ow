"""Round 121: 「要求作者修改」 on the review page (design 5.5.4, v6.17).

The user decided the review page's only direct action is an email to the
author: 「直接处置只做发信」.
"""

import pytest
from allauth.account.models import EmailAddress
from django.contrib.auth.models import Group
from django.core.management import call_command
from django.urls import reverse
from django.utils import timezone
from wagtail.models import ModelLogEntry

from accounts.models import User
from moderation import services
from moderation.models import ModerationItem, Risk, TargetType

PASSWORD = "Correct-Horse-Battery-1"


@pytest.fixture
def site(db):
    call_command("init_site", verbosity=0)


def _user(email, *groups, nickname=None):
    user = User.objects.create_user(
        email=email,
        password=PASSWORD,
        nickname=nickname or email.split("@")[0][:12],
        agreed_terms_at=timezone.now(),
        agreed_cross_border_at=timezone.now(),
    )
    EmailAddress.objects.create(user=user, email=email, verified=True, primary=True)
    for name in groups:
        user.groups.add(Group.objects.get(name=name))
    return user


def _item(author, **extra):
    values = {
        "target_type": TargetType.TEAM_DESCRIPTION,
        "target_id": 7,
        "field": "description",
        "url": "/teams/7/",
        "author": author,
        "excerpt": "欢迎新人！来的都是菜鸡，别来拖后腿。",
        "quote": "来的都是菜鸡",
        "text_hash": f"ask-{ModerationItem.objects.count()}",
        "risk": Risk.MEDIUM,
        "checked_at": timezone.now(),
    }
    values.update(extra)
    return ModerationItem.objects.create(**values)


@pytest.mark.django_db
def test_an_editor_writes_to_the_author(
    site, client, mailoutbox, django_capture_on_commit_callbacks
):
    author = _user("captain121@example.com", nickname="队长121")
    item = _item(author)
    editor = _user("editor121@example.com", "内容编辑")
    client.force_login(editor)
    detail = client.get(reverse("moderation_detail", args=[item.pk])).content.decode()
    assert "发信给作者" in detail
    with django_capture_on_commit_callbacks(execute=True):
        client.post(
            reverse("moderation_ask_author", args=[item.pk]),
            {"message": "简介里有贬低其他玩家的说法，请改一下。"},
        )
    assert len(mailoutbox) == 1
    letter = mailoutbox[0]
    assert letter.to == ["captain121@example.com"]
    assert "请修改你的战队简介" in letter.subject
    assert "简介里有贬低其他玩家的说法，请改一下。" in letter.body
    assert "来的都是菜鸡" in letter.body
    assert "/teams/7/manage/" in letter.body
    item.refresh_from_db()
    assert item.status == ModerationItem.Status.HANDLED
    assert item.reviewed_by == editor
    entry = ModelLogEntry.objects.for_instance(item).get(
        action=services.REVISE_LOG_ACTION
    )
    assert entry.data["note"] == "简介里有贬低其他玩家的说法，请改一下。"
    history = client.get(reverse("moderation_detail", args=[item.pk])).content.decode()
    assert "要求作者修改（已发信）" in history


@pytest.mark.django_db
def test_no_author_or_a_deactivated_one_gets_no_form_and_no_mail(
    site, client, mailoutbox
):
    client.force_login(_user("editor121b@example.com", "内容编辑"))
    orphan = _item(None)
    gone = _user("gone121@example.com")
    User.objects.filter(pk=gone.pk).update(is_active=False)
    stopped = _item(User.objects.get(pk=gone.pk))
    for item, reason in ((orphan, "没有作者"), (stopped, "已停用")):
        page = client.get(reverse("moderation_detail", args=[item.pk])).content.decode()
        assert reason in page
        assert "发信给作者" not in page
        client.post(
            reverse("moderation_ask_author", args=[item.pk]), {"message": "请修改。"}
        )
        item.refresh_from_db()
        assert item.status == ModerationItem.Status.PENDING
    assert mailoutbox == []


@pytest.mark.django_db
def test_an_empty_or_long_message_is_refused(site, client, mailoutbox):
    client.force_login(_user("editor121c@example.com", "内容编辑"))
    item = _item(_user("author121c@example.com"))
    for message in ("   ", "改" * (services.REVISE_MAX_CHARS + 1)):
        response = client.post(
            reverse("moderation_ask_author", args=[item.pk]),
            {"message": message},
            follow=True,
        )
        assert response.status_code == 200
        item.refresh_from_db()
        assert item.status == ModerationItem.Status.PENDING
    assert mailoutbox == []


@pytest.mark.django_db
def test_only_reviewers_can_write(site, client, mailoutbox):
    item = _item(_user("author121d@example.com"))
    client.force_login(_user("manager121@example.com", "赛事管理员"))
    response = client.post(
        reverse("moderation_ask_author", args=[item.pk]), {"message": "请修改。"}
    )
    assert response.status_code in (302, 403)
    item.refresh_from_db()
    assert item.status == ModerationItem.Status.PENDING
    assert mailoutbox == []


def test_each_kind_of_content_has_somewhere_to_fix_it():
    from types import SimpleNamespace

    from moderation.notifications import revise_url

    def url(kind, address=""):
        return revise_url(SimpleNamespace(target_type=kind, target_id=5, url=address))

    assert url("nickname").endswith("/me/")
    assert url("team_name").endswith("/teams/5/manage/")
    assert url("team_description").endswith("/teams/5/manage/")
    assert url("article").endswith("/admin/articles/5/")
    assert url("page").endswith("/admin/pages/5/")
    assert url("tournament_description").endswith("/admin/tournaments/edit/5/")
    assert url("scrim_description").endswith("/admin/scrims/edit/5/")
    assert url("comment", "/news/a/#comment-9").endswith("/news/a/#comment-9")
    assert url("image") == ""


def test_the_letter_is_on_the_specimen_page():
    from core.email_samples import sample

    found = sample("ask-author")
    assert found is not None
    assert "去修改" in found.text
