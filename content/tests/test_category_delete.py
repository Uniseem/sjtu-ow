"""Round 176: a category articles still use cannot be deleted (design 5.3,
v6.59). Before, confirming the delete was a server error (PROTECT)."""

import pytest
from django.core.management import call_command
from django.test import Client

from content.models import ArticleCategory

LIST = "/admin/snippets/content/articlecategory/"


def _delete_url(category):
    return f"{LIST}delete/{category.pk}/"


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
    html = client.get(LIST).content.decode()
    assert _delete_url(empty) in html
    assert _delete_url(used) not in html


def test_a_used_category_says_why_and_stays(editor_and_categories):
    client, used, empty = editor_and_categories
    for response in (client.get(_delete_url(used)), client.post(_delete_url(used))):
        assert response.status_code == 302
        assert response["Location"].endswith(f"edit/{used.pk}/")
    page = client.get(f"{LIST}edit/{used.pk}/").content.decode()
    assert "篇文章在" in page and "先把它们改到别的分类再删" in page
    assert ArticleCategory.objects.filter(pk=used.pk).exists()


def test_bulk_delete_skips_it(editor_and_categories):
    client, used, empty = editor_and_categories
    url = f"/admin/bulk/content/articlecategory/delete/?id={used.pk}&id={empty.pk}"
    response = client.post(url)
    assert response.status_code != 500
    assert ArticleCategory.objects.filter(pk=used.pk).exists()
    assert not ArticleCategory.objects.filter(pk=empty.pk).exists()


def test_an_empty_one_still_goes(editor_and_categories):
    client, used, empty = editor_and_categories
    assert client.post(_delete_url(empty)).status_code == 302
    assert not ArticleCategory.objects.filter(pk=empty.pk).exists()
