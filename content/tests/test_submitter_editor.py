"""Round 130: a plain member's article form leaves out the address, search
text and schedule (design 14.3, v6.25). They are left out of the form, not
hidden in it, so saving again keeps what an editor set. Since v7.0 the form
is the back office's (backoffice.forms.ArticleForm, docs/admin.md 4.2).
"""

import pytest
from django.core.management import call_command
from django.urls import reverse
from wagtail.test.utils.form_data import querydict_from_html

from accounts.tests.test_onboarding import _user
from backoffice.forms import EDITOR_ONLY_FIELDS, ArticleForm
from content.models import ArticleCategory, ArticleIndexPage, ArticlePage


@pytest.fixture
def news(db):
    call_command("init_site", verbosity=0)
    return ArticleIndexPage.objects.get(slug="news")


def _add_url():
    return reverse("backoffice:article_new")


def _save(client, url, **changes):
    """Fill in the form the way the page renders it, then save a draft."""
    page = client.get(url)
    assert page.status_code == 200
    data = querydict_from_html(page.content.decode(), form_index=0)
    data["category"] = str(ArticleCategory.objects.get(slug="guide").pk)
    data["save"] = "1"
    for name, value in changes.items():
        data[name] = value
    response = client.post(url, data)
    assert response.status_code == 302, response.context["form"].errors
    return response


@pytest.mark.django_db
def test_only_editors_and_authors_get_the_promote_fields(news, client):
    writer = _user("w130@example.com", "投稿者")
    editor = _user("e130@example.com", "内容编辑", "投稿者")
    author = _user("a130@example.com", "认证作者", "投稿者")
    for user, sees in ((writer, False), (editor, True), (author, True)):
        form = ArticleForm(instance=ArticlePage(owner=user), parent=news, user=user)
        for name in EDITOR_ONLY_FIELDS:
            assert (name in form.fields) is sees, (user.email, name)

    client.force_login(writer)
    html = client.get(_add_url()).content.decode()
    assert 'name="seo_title"' not in html
    assert 'name="slug"' not in html
    assert 'name="go_live_at"' not in html
    client.force_login(editor)
    html = client.get(_add_url()).content.decode()
    assert 'name="seo_title"' in html
    assert 'name="slug"' in html


@pytest.mark.django_db
def test_the_address_comes_from_the_title_and_survives_the_writer(news, client):
    writer = _user("w130b@example.com", "投稿者")
    client.force_login(writer)
    _save(client, _add_url(), title="我的第一篇攻略")
    page = ArticlePage.objects.get(title="我的第一篇攻略")
    assert page.slug == "我的第一篇攻略"

    # The editor gives it a proper address and search text.
    page.slug = "first-guide"
    page.seo_title = "新手攻略合集"
    page.save()
    page.save_revision()

    edit = reverse("backoffice:article_edit", args=[page.pk])
    _save(client, edit, title="我的第一篇攻略（修订）")
    latest = ArticlePage.objects.get(pk=page.pk).get_latest_revision_as_object()
    assert latest.title == "我的第一篇攻略（修订）"
    assert latest.slug == "first-guide"
    assert latest.seo_title == "新手攻略合集"


@pytest.mark.django_db
def test_reserved_and_taken_addresses_step_aside(news, client):
    client.force_login(_user("w130c@example.com", "投稿者"))
    _save(client, _add_url(), title="admin")
    assert ArticlePage.objects.get(title="admin").slug == "admin-article"
    _save(client, _add_url(), title="Admin")
    assert ArticlePage.objects.get(title="Admin").slug == "admin-article-2"


@pytest.mark.django_db
def test_an_editor_s_taken_address_is_refused_on_the_field(news, client):
    editor = _user("e196@example.com", "内容编辑", "投稿者")
    client.force_login(editor)
    _save(client, _add_url(), title="第一篇", slug="taken-196")
    page = client.get(_add_url())
    data = querydict_from_html(page.content.decode(), form_index=0)
    data.update(
        {
            "title": "第二篇",
            "slug": "taken-196",
            "category": str(ArticleCategory.objects.get(slug="guide").pk),
            "save": "1",
        }
    )
    response = client.post(_add_url(), data)
    assert response.status_code == 200
    assert "这个网址片段已经有文章在用了" in response.content.decode()
    assert ArticlePage.objects.filter(slug="taken-196").count() == 1
