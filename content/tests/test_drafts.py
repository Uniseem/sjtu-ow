"""Round 205 (design 13.17, v7.9): articles, plain pages, the homepage's pins
and the news section's intro save themselves as drafts; 「发布」 makes them
live. One person's stretch of editing is one revision; a new article exists
from its first change, empty title and category included; the address of an
article never published follows its title.
"""

import json
import re
from datetime import timedelta
from pathlib import Path

import pytest
from django.conf import settings
from django.core.management import call_command
from django.urls import reverse
from django.utils import timezone
from wagtail.models import PageLogEntry, Revision

from accounts.services import GROUP_SUBMITTER
from accounts.tests.test_onboarding import _user
from backoffice.tests.test_backoffice import _article
from content.drafts import UNTITLED
from content.models import ArticleCategory, ArticleIndexPage, ArticlePage, HomePage

AUTOSAVE = {"HTTP_X_AUTOSAVE": "1", "HTTP_ACCEPT": "application/json"}


@pytest.fixture
def site(db):
    call_command("init_site", verbosity=0)


def _draft(page):
    """The page as its latest revision has it."""
    return type(page).objects.get(pk=page.pk).get_latest_revision_as_object()


def _fields(page, **changes):
    data = {
        "title": page.title,
        "category": page.category_id or "",
        "summary": page.summary,
        "body": page.body,
    }
    data.update(changes)
    return data


def _save(client, url, data):
    return json.loads(client.post(url, data, **AUTOSAVE).content)


def _revisions(page):
    return Revision.objects.filter(object_id=str(page.pk)).count()


@pytest.mark.django_db
def test_an_article_saves_itself_as_a_draft(site, client):
    writer = _user("draft205@example.com", GROUP_SUBMITTER)
    page = _article(writer, title="草稿205", live=True)
    client.force_login(writer)
    edit = reverse("backoffice:article_edit", args=[page.pk])
    answer = _save(client, edit, _fields(page, body="自动存的正文"))
    assert answer["ok"] and answer["saved"] == ["body"]
    page.refresh_from_db()
    assert page.body == "正文" and page.has_unpublished_changes  # still as published
    assert page.get_latest_revision_as_object().body == "自动存的正文"
    assert "正文" in client.get(page.url).content.decode()


@pytest.mark.django_db
def test_one_stretch_of_editing_is_one_revision(site, client):
    writer = _user("stretch205@example.com", GROUP_SUBMITTER)
    page = _article(writer, title="一份205", live=True)
    client.force_login(writer)
    edit = reverse("backoffice:article_edit", args=[page.pk])
    before = _revisions(page)
    for text in ("第一遍", "第二遍", "第三遍"):
        _save(client, edit, _fields(page, body=text))
    assert _revisions(page) == before + 1
    page.refresh_from_db()
    assert page.get_latest_revision_as_object().body == "第三遍"
    edits = PageLogEntry.objects.filter(page=page, action="wagtail.edit", user=writer)
    assert edits.count() == 1

    # Half an hour later, or after it was published, the next one is new.
    Revision.objects.filter(pk=page.latest_revision_id).update(
        created_at=timezone.now() - timedelta(minutes=31)
    )
    _save(client, edit, _fields(page, body="隔了半小时"))
    assert _revisions(page) == before + 2
    client.post(edit, {**_fields(page, body="发布的这一版"), "publish": "1"})
    published = _revisions(page)
    _save(client, edit, _fields(page, body="发布以后接着改"))
    assert _revisions(page) == published + 1
    page.refresh_from_db()
    assert page.body == "发布的这一版"


@pytest.mark.django_db
def test_someone_else_starts_their_own_draft(site, client):
    writer = _user("first205@example.com", GROUP_SUBMITTER)
    page = _article(writer, title="两个人205", live=True)
    editor = _user("second205@example.com", "内容编辑")
    edit = reverse("backoffice:article_edit", args=[page.pk])
    client.force_login(writer)
    _save(client, edit, _fields(page, body="作者改的"))
    mine = _revisions(page)
    client.force_login(editor)
    _save(client, edit, _fields(page, body="编辑接着改的"))
    assert _revisions(page) == mine + 1
    page.refresh_from_db()
    assert page.latest_revision.user == editor


@pytest.mark.django_db
def test_a_new_article_exists_from_its_first_change(site, client):
    writer = _user("new205@example.com", GROUP_SUBMITTER)
    client.force_login(writer)
    answer = _save(client, reverse("backoffice:article_new"), {"body": "先写正文"})
    page = ArticlePage.objects.get(owner=writer)
    assert answer["location"] == reverse("backoffice:article_edit", args=[page.pk])
    assert set(answer["errors"]) == {"title", "category"}  # said, and saved anyway
    assert not page.live and page.category is None and page.title == UNTITLED
    assert page.get_latest_revision_as_object().body == "先写正文"
    assert page.get_latest_revision_as_object().title == ""

    listing = client.get(reverse("backoffice:articles")).content.decode()
    assert "（无标题）" in listing and "未选分类" in listing
    edit = client.get(answer["location"]).content.decode()
    assert re.search(r'name="title"[^>]*value="[^"]', edit) is None  # empty box
    assert "先写正文" in edit

    refused = client.post(answer["location"], {"body": "先写正文", "publish": "1"})
    assert refused.status_code == 200  # the form again, with what is missing
    page.refresh_from_db()
    assert not page.live

    guide = ArticleCategory.objects.get(slug="guide")
    client.post(
        answer["location"],
        {"title": "补上标题", "category": guide.pk, "body": "先写正文", "publish": "1"},
    )
    page.refresh_from_db()
    assert page.live and page.title == "补上标题" and page.category == guide


@pytest.mark.django_db
def test_the_address_follows_the_title_until_published(site, client):
    editor = _user("slug205@example.com", "内容编辑")
    client.force_login(editor)
    guide = ArticleCategory.objects.get(slug="guide")
    answer = _save(client, reverse("backoffice:article_new"), {"title": "新"})
    page = ArticlePage.objects.get(owner=editor)
    assert page.get_latest_revision_as_object().slug == "新"
    edit = answer["location"]
    fields = {"title": "新赛季开始了", "category": guide.pk, "body": "x", "slug": "新"}
    answer = _save(client, edit, fields)
    assert answer["values"] == {"slug": "新赛季开始了"}  # the page shows it
    assert _draft(page).slug == "新赛季开始了"

    # Typed by the editor: kept, whatever the title does next.
    _save(client, edit, {**fields, "slug": "season"})
    _save(client, edit, {**fields, "title": "又改了标题", "slug": "season"})
    assert _draft(page).slug == "season"

    # Published: the address stays.
    client.post(edit, {**fields, "slug": "", "publish": "1"})
    live = ArticlePage.objects.get(pk=page.pk)
    assert live.live and live.slug == "新赛季开始了"
    _save(client, edit, {**fields, "title": "发布以后的新标题", "slug": live.slug})
    assert _draft(page).slug == "新赛季开始了"


@pytest.mark.django_db
def test_a_bad_field_keeps_its_value_and_the_rest_is_saved(site, client):
    writer = _user("partial205@example.com", GROUP_SUBMITTER)
    page = _article(writer, title="留着标题205", live=True)
    client.force_login(writer)
    edit = reverse("backoffice:article_edit", args=[page.pk])
    answer = _save(client, edit, _fields(page, title="", body="正文照存"))
    assert "title" in answer["errors"] and answer["saved"] == ["body"]
    draft = ArticlePage.objects.get(pk=page.pk).get_latest_revision_as_object()
    assert (draft.title, draft.body) == ("留着标题205", "正文照存")


@pytest.mark.django_db
def test_a_plain_page_waits_for_publish(site, client):
    from content.models import StandardPage

    about = StandardPage.objects.get(slug="about")
    before = about.body
    client.force_login(_user("about205@example.com", "内容编辑"))
    edit = reverse("backoffice:page_edit", args=[about.pk])
    answer = _save(client, edit, {"title": about.title, "body": "草稿里的关于我们"})
    assert answer["ok"] and answer["saved"] == ["body"]
    about.refresh_from_db()
    assert about.body == before
    assert about.get_latest_revision_as_object().body == "草稿里的关于我们"


@pytest.mark.django_db
def test_the_pins_and_the_intro_wait_for_publish(site, client):
    writer = _user("pins205@example.com", GROUP_SUBMITTER)
    first = _article(writer, title="置顶205", live=True)
    client.force_login(_user("pinner205@example.com", "内容编辑"))
    pins = reverse("backoffice:home_pins")
    assert _save(client, pins, {"article_1": first.pk})["ok"]
    home = HomePage.objects.get()
    assert not home.pinned_articles.exists() and home.has_unpublished_changes
    assert [r.article_id for r in _draft(home).pinned_articles.all()] == [first.pk]
    listing = client.get(reverse("backoffice:pages")).content.decode()
    assert listing.count("data-unpublished") == 1
    client.post(pins, {"article_1": first.pk, "publish": "1"})
    live = HomePage.objects.get().pinned_articles.all()
    assert [rel.article_id for rel in live] == [first.pk]

    intro = reverse("backoffice:index_intro")
    assert _save(client, intro, {"intro": "草稿介绍"})["ok"]
    news = ArticleIndexPage.objects.get(slug="news")
    assert news.intro != "草稿介绍" and _draft(news).intro == "草稿介绍"
    client.post(intro, {"intro": "草稿介绍", "publish": "1"})
    assert ArticleIndexPage.objects.get(slug="news").intro == "草稿介绍"


def test_the_editor_saves_after_a_pause_not_per_keystroke():
    """It reports typing as ``input`` (autosave waits 0.8 s) and ``change``
    only once it is left; a change per keystroke saved per keystroke."""
    source = (Path(settings.BASE_DIR) / "static/js/markdown-editor.js").read_text(
        encoding="utf-8"
    )
    on_change = source.split('editor.codemirror.on("change"', 1)[1].split("});", 1)[0]
    assert 'new Event("input"' in on_change and 'new Event("change"' not in on_change
    on_blur = source.split('editor.codemirror.on("blur"', 1)[1].split("});", 1)[0]
    assert 'new Event("change"' in on_blur
