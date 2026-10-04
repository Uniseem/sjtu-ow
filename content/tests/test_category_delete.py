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
