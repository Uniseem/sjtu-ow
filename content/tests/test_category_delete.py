"""Round 176: a category articles still use cannot be deleted (design 5.3,
v6.59). Before, confirming the delete was a server error (PROTECT). Since
v7.0 the list is the back office's 「内容 → 分类」 (docs/admin.md 4.2)."""

import pytest
from django.core.management import call_command
from django.test import Client
from django.urls import reverse

from content.models import ArticleCategory


def _delete_url(category):
    return reverse("backoffice:category_delete", args=[category.pk])


@pytest.fixture
def editor_and_categories(db):
    from accounts.tests.test_onboarding import _user
    from core.tests.test_chapter15_audit import _publish_article, _verified, make_user

    call_command("init_site", verbosity=0)
    used = _publish_article(_verified(make_user(1))).category
    empty = ArticleCategory.objects.create(name="空分类176", slug="empty-176")
    client = Client(raise_request_exception=False)
    client.force_login(_user("c176@example.com", "内容编辑", "投稿者"))
    return client, used, empty


def test_only_empty_categories_offer_delete(editor_and_categories):
    client, used, empty = editor_and_categories
    html = client.get(reverse("backoffice:categories")).content.decode()
    assert _delete_url(empty) in html
    assert _delete_url(used) not in html
    edit = client.get(reverse("backoffice:category_edit", args=[used.pk]))
    assert _delete_url(used) not in edit.content.decode()


def test_a_used_category_says_why_and_stays(editor_and_categories):
    client, used, empty = editor_and_categories
    response = client.post(_delete_url(used))
    assert response.status_code == 302
    assert response["Location"] == reverse("backoffice:category_edit", args=[used.pk])
    page = client.get(response["Location"]).content.decode()
    assert "篇文章在" in page and "先把它们改到别的分类再删" in page
    assert ArticleCategory.objects.filter(pk=used.pk).exists()
    # Only POST deletes; a typed address is no way round it.
    assert client.get(_delete_url(used)).status_code == 405


def test_an_empty_one_still_goes(editor_and_categories):
    client, used, empty = editor_and_categories
    assert client.post(_delete_url(empty)).status_code == 302
    assert not ArticleCategory.objects.filter(pk=empty.pk).exists()


# --- round 212, D2: drafts count too ---------------------------------------------

AUTOSAVE = {"HTTP_X_AUTOSAVE": "1", "HTTP_ACCEPT": "application/json"}


def _draft_only_reference(client, category):
    """An article whose category exists only in its latest draft revision:
    created unnamed, the category chosen afterwards by autosave."""
    import json

    from django.urls import reverse

    from content.models import ArticlePage

    url = reverse("backoffice:article_new")
    answer = json.loads(client.post(url, {"title": "草稿引用212"}, **AUTOSAVE).content)
    page = ArticlePage.objects.get(title="草稿引用212")
    assert page.category_id is None  # the row; the revision holds the choice
    edit = answer["location"]
    answer = json.loads(
        client.post(
            edit,
            {
                "title": "草稿引用212",
                "category": category.pk,
                "summary": "",
                "body": "",
            },
            **AUTOSAVE,
        ).content
    )
    assert answer["ok"]
    return page, edit


def test_a_category_used_only_by_a_draft_still_cannot_go(db):
    from django.core.management import call_command
    from django.test import Client

    from accounts.tests.test_onboarding import _user
    from content.models import ArticleCategory

    call_command("init_site", verbosity=0)
    client = Client()
    client.force_login(_user("d2-212@example.com", "内容编辑", "投稿者"))
    category = ArticleCategory.objects.create(name="草稿专用212", slug="draft-only-212")
    page, edit = _draft_only_reference(client, category)

    listing = client.get(reverse("backoffice:categories")).content.decode()
    assert _delete_url(category) not in listing  # the button is not offered
    response = client.post(_delete_url(category))
    assert response.status_code == 302
    assert ArticleCategory.objects.filter(pk=category.pk).exists()
    notice = client.get(response["Location"]).content.decode()
    assert "先把它们改到别的分类再删" in notice
    # And the article's edit page keeps working.
    assert client.get(edit).status_code == 200
    assert page.get_latest_revision_as_object().category == category


def test_a_scheduled_revision_also_counts(db):
    """A newer draft moved the article off the category, but the revision
    scheduled to go live still names it — publishing it would 500."""
    from datetime import timedelta

    from django.core.management import call_command
    from django.test import Client
    from django.utils import timezone
    from wagtail.models import Revision

    from accounts.tests.test_onboarding import _user
    from content.models import ArticleCategory
    from content.services import category_in_use

    call_command("init_site", verbosity=0)
    client = Client()
    client.force_login(_user("d2sched@example.com", "内容编辑", "投稿者"))
    category = ArticleCategory.objects.create(name="定时专用212", slug="sched-212")
    page, _edit = _draft_only_reference(client, category)
    scheduled = page.latest_revision_id
    from django.urls import reverse

    # Another editor's save is a new revision (one's own stretch overwrites);
    # the scheduled one is no longer the latest but still names the category.
    other = Client()
    other.force_login(_user("d2sched2@example.com", "内容编辑"))
    other.post(
        reverse("backoffice:article_edit", args=[page.pk]),
        {"title": "草稿引用212", "category": "", "summary": "", "body": ""},
        **AUTOSAVE,
    )
    page.refresh_from_db()
    assert page.latest_revision_id != scheduled
    Revision.objects.filter(pk=scheduled).update(
        approved_go_live_at=timezone.now() + timedelta(days=1)
    )
    assert category_in_use(category) == 1
    response = client.post(_delete_url(category))
    assert response.status_code == 302
    assert ArticleCategory.objects.filter(pk=category.pk).exists()
