"""Round 130: a submitter's editor leaves out the 「推荐」 tab (design 14.3, v6.25).

The address, search text, menu switch and schedule are the editor's. They
are left out of the submitter's form, not hidden in it, so saving again
keeps what the editor set.
"""

import pytest
from django.core.management import call_command
from django.urls import reverse
from wagtail.test.utils.form_data import querydict_from_html

from accounts.tests.test_onboarding import _user
from content.forms import EDITOR_ONLY_FIELDS
from content.models import ArticleCategory, ArticleIndexPage, ArticlePage


@pytest.fixture
def news(db):
    call_command("init_site", verbosity=0)
    return ArticleIndexPage.objects.get(slug="news")


def _add_url(news):
    return reverse("wagtailadmin_pages:add", args=["content", "articlepage", news.pk])


def _save(client, url, **changes):
    """Fill in the form the way the page renders it, then save a draft."""
    page = client.get(url)
    assert page.status_code == 200
    data = querydict_from_html(page.content.decode(), form_id="page-edit-form")
    data["category"] = str(ArticleCategory.objects.get(slug="guide").pk)
    data["body-count"] = "0"  # the StreamField is drawn by script
    for name, value in changes.items():
        data[name] = value
    response = client.post(url, data)
    assert response.status_code == 302, response.context["form"].errors
    return response


@pytest.mark.django_db
def test_only_editors_and_authors_get_the_promote_fields(news, client):
    form_class = ArticlePage.get_edit_handler().get_form_class()
    writer = _user("w130@example.com", "投稿者")
    editor = _user("e130@example.com", "内容编辑", "投稿者")
    author = _user("a130@example.com", "认证作者", "投稿者")
    for user, sees in ((writer, False), (editor, True), (author, True)):
        form = form_class(
            instance=ArticlePage(owner=user), parent_page=news, for_user=user
        )
        for name in EDITOR_ONLY_FIELDS:
            assert (name in form.fields) is sees, (user.email, name)

    client.force_login(writer)
    html = client.get(_add_url(news)).content.decode()
    assert 'name="seo_title"' not in html
    assert 'name="slug"' not in html
    assert 'name="go_live_at"' not in html
    client.force_login(editor)
    html = client.get(_add_url(news)).content.decode()
    assert 'name="seo_title"' in html
    assert 'name="slug"' in html


@pytest.mark.django_db
def test_the_address_comes_from_the_title_and_survives_the_writer(news, client):
    writer = _user("w130b@example.com", "投稿者")
    client.force_login(writer)
    _save(client, _add_url(news), title="我的第一篇攻略")
    page = ArticlePage.objects.get(title="我的第一篇攻略")
    assert page.slug == "我的第一篇攻略"

    # The editor gives it a proper address and search text.
    page.slug = "first-guide"
    page.seo_title = "新手攻略合集"
    page.save()
    page.save_revision()

    edit = reverse("wagtailadmin_pages:edit", args=[page.pk])
    _save(client, edit, title="我的第一篇攻略（修订）")
    latest = ArticlePage.objects.get(pk=page.pk).get_latest_revision_as_object()
    assert latest.title == "我的第一篇攻略（修订）"
    assert latest.slug == "first-guide"
    assert latest.seo_title == "新手攻略合集"


@pytest.mark.django_db
def test_reserved_and_taken_addresses_step_aside(news, client):
    client.force_login(_user("w130c@example.com", "投稿者"))
    _save(client, _add_url(news), title="admin")
    assert ArticlePage.objects.get(title="admin").slug == "admin-article"
    _save(client, _add_url(news), title="Admin")
    assert ArticlePage.objects.get(title="Admin").slug == "admin-article-2"
