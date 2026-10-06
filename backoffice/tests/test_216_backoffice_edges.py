"""Round 216: the back office's edges (review B4, B5, B7, B8, B9, B10, F5,
F6, F7, F9).

Oversized ids in the pins form, a prerender path that cannot be rendered,
a new article's first save sent twice, empty drafts left behind, a clashing
address on a form without the address field, the 「发布」 button for people
who cannot publish, the avatar review's way back on HTTPS, the picture
picker's spoken names, and the script guards behind autosave and the
picture dialog.
"""

import io
import json
from datetime import timedelta
from pathlib import Path
from unittest import mock

import pytest
from django import forms
from django.conf import settings
from django.contrib.auth.models import Group, Permission
from django.contrib.messages import get_messages
from django.core.management import call_command
from django.urls import reverse
from django.utils import timezone
from wagtail.models import GroupPagePermission, Page

from accounts.models import User
from accounts.services import GROUP_SUBMITTER
from accounts.tests.test_onboarding import _user
from backoffice.forms import ArticleForm, PinnedArticlesForm
from backoffice.tests.test_backoffice import _article, _root
from backoffice.widgets import image_field
from content.drafts import start_article
from content.models import ArticleCategory, ArticleIndexPage, ArticlePage
from content.services import first_article_index
from core.models import PrerenderedPage
from scrims.models import Scrim, ScrimFormat, ScrimStatus
from tournaments.models import Tournament, TournamentStatus

AUTOSAVE = {"HTTP_X_AUTOSAVE": "1", "HTTP_ACCEPT": "application/json"}
HUGE = "99999999999999999999"  # twenty digits, past any SQLite integer


@pytest.fixture
def site(db):
    call_command("init_site", verbosity=0)


def _read(relative):
    return (Path(settings.BASE_DIR) / relative).read_text(encoding="utf-8")


# --- B4: the pins form takes any id -------------------------------------------


@pytest.mark.django_db
@pytest.mark.parametrize("value", [HUGE, "abc"])
def test_the_pins_form_refuses_what_is_not_an_id(site, value):
    """216, B4: twenty digits through a Wagtail page's key were an
    OverflowError (a 500); now the slot is simply not a choice."""
    form = PinnedArticlesForm(data={"article_1": value})

    assert not form.is_valid()
    assert "article_1" in form.errors


@pytest.mark.django_db
@pytest.mark.parametrize("value", [HUGE, "abc"])
def test_posting_a_huge_pin_is_not_a_500(site, client, value):
    """216, B4: the same through the page, as a content editor."""
    client.force_login(_user("pins216@example.com", "内容编辑"))

    response = client.post(reverse("backoffice:home_pins"), {"article_1": value})

    assert response.status_code in (200, 302)


# --- B5, F9: what autosave.js does with answers and chosen files --------------


def test_an_answer_does_not_overwrite_what_was_typed_since():
    """216, B5: a value the server sends back is not put into a text box
    whose content changed after this save was sent (a substring guard)."""
    source = _read("static/js/autosave.js")
    save = source.split("Saver.prototype.save = function", 1)[1]
    assert "this.sent = body" in save.split(".fetch(", 1)[0]
    values = source.split("Object.keys(data.values || {})", 1)[1]
    values = values.split("});", 1)[0]
    assert "sent.has(name)" in values
    assert "String(sent.get(name)) !== control.value" in values


def test_a_chosen_avatar_goes_through_the_submit_event():
    """216, F9: ``form.submit()`` skipped the submit event, so unsaved
    changes elsewhere were not saved first. The automatic upload now waits
    for them and uses ``requestSubmit`` (a substring guard)."""
    source = _read("static/js/autosave.js")
    block = source.split('form.hasAttribute("data-autosubmit-file")', 1)[1]
    block = block.split("var saver = form && saverFor(form);", 1)[0]
    assert "flushAll().then(" in block
    assert "form.requestSubmit()" in block
    assert block.index("flushAll().then(") < block.index("form.requestSubmit()")


# --- B7: a prerender path that cannot be rendered -----------------------------


@pytest.mark.django_db
@pytest.mark.parametrize("path", ["no-slash", "/a?b"])
def test_rebuilding_a_bad_path_says_so_and_queues_nothing(site, client, settings, path):
    """216, B7: such a path was 「已排入队列」 though nothing was queued."""
    settings.PRERENDER_ENABLED = True
    client.force_login(_root("root216@example.com"))
    rows = PrerenderedPage.objects.count()
    with mock.patch("core.prerender.request_page") as request_page:
        response = client.post(reverse("core_prerender_rebuild"), {"path": path})

    assert response.status_code == 302
    request_page.assert_not_called()
    assert PrerenderedPage.objects.count() == rows
    texts = [str(message) for message in get_messages(response.wsgi_request)]
    assert any("不是能生成的页面地址" in text for text in texts), texts
    assert not any("已排入队列" in text for text in texts), texts


@pytest.mark.django_db
def test_rebuilding_a_good_path_still_queues_it(site, client, settings):
    """The other side of B7."""
    settings.PRERENDER_ENABLED = True
    client.force_login(_root("root216b@example.com"))
    with mock.patch("core.prerender.request_page") as request_page:
        response = client.post(reverse("core_prerender_rebuild"), {"path": "/news/"})

    request_page.assert_called_once_with("/news/")
    texts = [str(message) for message in get_messages(response.wsgi_request)]
    assert any("已排入队列：/news/" in text for text in texts), texts


# --- B8: a new article's first save, sent twice -------------------------------


def _first_save(client, key, title="重放216"):
    guide = ArticleCategory.objects.get(slug="guide")
    response = client.post(
        reverse("backoffice:article_new"),
        {"title": title, "category": guide.pk, "summary": "", "body": ""},
        HTTP_X_AUTOSAVE_KEY=key,
        **AUTOSAVE,
    )
    assert response.status_code == 200
    return json.loads(response.content)


@pytest.mark.django_db
def test_a_retried_first_save_makes_one_article(site, client):
    """216, B8: the answer to the first save was lost and the script sent
    it again to 「新建」, making a second article. The same key is now told
    where the first one went."""
    client.force_login(_user("replay216@example.com", GROUP_SUBMITTER))
    key = "AbCdEfGhIjKlMnOpQrStUv12"

    first = _first_save(client, key)
    again = _first_save(client, key)

    assert ArticlePage.objects.filter(title="重放216").count() == 1
    page = ArticlePage.objects.get(title="重放216")
    assert first["location"] == reverse("backoffice:article_edit", args=[page.pk])
    assert again["retry"] is True
    assert again["location"] == first["location"]
    assert "retry" not in first


@pytest.mark.django_db
def test_another_key_is_another_article(site, client):
    """The other side of B8: a second form (another key) is a second article."""
    client.force_login(_user("replay216b@example.com", GROUP_SUBMITTER))

    first = _first_save(client, "A" * 24)
    second = _first_save(client, "B" * 24)

    assert ArticlePage.objects.filter(title="重放216").count() == 2
    assert first["location"] != second["location"]
    assert "retry" not in second


# --- B8: empty drafts are cleared after a week --------------------------------


def _new_article(user, title, slug):
    news = ArticleIndexPage.objects.get(slug="news")
    page = ArticlePage(owner=user, author=user, title=title, slug=slug, body="")
    return start_article(news, page, user)


def _age(model, pk, field, days):
    model.objects.filter(pk=pk).update(**{field: timezone.now() - timedelta(days=days)})


@pytest.mark.django_db
def test_cleanup_removes_drafts_that_never_got_a_word(site):
    """216, B8: every 「新建」 opened and left made an empty draft. A week
    later, never published and still without a title or text, it goes."""
    user = _user("empty216@example.com", GROUP_SUBMITTER)
    old_empty = _new_article(user, "", "empty216-old")
    titled = _new_article(user, "有标题216", "empty216-titled")
    young_empty = _new_article(user, "", "empty216-young")
    _age(ArticlePage, old_empty.pk, "latest_revision_created_at", 8)
    _age(ArticlePage, titled.pk, "latest_revision_created_at", 8)

    def tournament(**changes):
        options = {
            "title": "",
            "description": "",
            "status": TournamentStatus.DRAFT,
            "registration_opens_at": None,
            "registration_closes_at": None,
            "published_at": None,
        }
        options.update(changes)
        return Tournament.objects.create(**options)

    empty_tournament = tournament()
    once_published = tournament(published_at=timezone.now() - timedelta(days=30))
    named_tournament = tournament(title="春季赛216")
    young_tournament = tournament()
    for row in (empty_tournament, once_published, named_tournament):
        _age(Tournament, row.pk, "updated_at", 8)

    def scrim(**changes):
        options = {
            "title": "",
            "description": "",
            "status": ScrimStatus.DRAFT,
            "format": ScrimFormat.RQ_5V5,
        }
        options.update(changes)
        return Scrim.objects.create(**options)

    empty_scrim = scrim()
    described_scrim = scrim(description="周五晚上")
    young_scrim = scrim()
    for row in (empty_scrim, described_scrim):
        _age(Scrim, row.pk, "updated_at", 8)

    call_command("cleanup_old_data", stdout=io.StringIO())

    assert not ArticlePage.objects.filter(pk=old_empty.pk).exists()
    assert ArticlePage.objects.filter(pk=titled.pk).exists()
    assert ArticlePage.objects.filter(pk=young_empty.pk).exists()
    assert not Tournament.objects.filter(pk=empty_tournament.pk).exists()
    assert Tournament.objects.filter(pk=once_published.pk).exists()
    assert Tournament.objects.filter(pk=named_tournament.pk).exists()
    assert Tournament.objects.filter(pk=young_tournament.pk).exists()
    assert not Scrim.objects.filter(pk=empty_scrim.pk).exists()
    assert Scrim.objects.filter(pk=described_scrim.pk).exists()
    assert Scrim.objects.filter(pk=young_scrim.pk).exists()


@pytest.mark.django_db
def test_a_dry_run_counts_the_empty_drafts_and_keeps_them(site):
    """B8 with ``--dry-run``: counted, not deleted."""
    user = _user("dry216@example.com", GROUP_SUBMITTER)
    page = _new_article(user, "", "dry216")
    _age(ArticlePage, page.pk, "latest_revision_created_at", 8)
    out = io.StringIO()

    call_command("cleanup_old_data", "--dry-run", stdout=out)

    assert ArticlePage.objects.filter(pk=page.pk).exists()
    assert "空着的草稿" in out.getvalue()


# --- B9: a clashing address on a form without the address field ---------------


@pytest.fixture
def clashing(site):
    """A plain member's draft whose address a sibling took meanwhile."""
    member = _user("clash216@example.com", GROUP_SUBMITTER)
    mine = _article(member, title="撞车216")
    other = _article(member, title="另一篇216")
    Page.objects.filter(pk=other.pk).update(slug=mine.slug)
    return member, mine


def _article_data(page):
    return {
        "title": page.title,
        "category": page.category_id,
        "summary": page.summary,
        "body": page.body,
    }


@pytest.mark.django_db
def test_a_clashing_address_is_a_form_error_not_a_crash(clashing):
    """216, B9: Wagtail reports the clash on ``slug``, which plain members'
    form leaves out; Django raised ValueError (no such field), a 500."""
    member, mine = clashing
    draft = mine.get_latest_revision_as_object()
    form = ArticleForm(
        _article_data(mine), instance=draft, user=member, parent=mine.get_parent()
    )
    assert "slug" not in form.fields

    assert not form.is_valid()
    assert form.non_field_errors()


@pytest.mark.django_db
def test_autosaving_a_clashing_address_answers_with_the_error(clashing, client):
    """B9 through the page: the autosave answer carries the error."""
    member, mine = clashing
    client.force_login(member)

    response = client.post(
        reverse("backoffice:article_edit", args=[mine.pk]),
        _article_data(mine),
        **AUTOSAVE,
    )

    assert response.status_code == 200
    answer = json.loads(response.content)
    assert answer["ok"] is False
    assert answer["errors"].get("__all__")


# --- B10: 「发布」 only for those who may publish ---------------------------------


@pytest.mark.django_db
def test_the_publish_button_needs_publish_permission(site, client):
    """216, B10: a new article showed 「发布」 to everyone; a writer who may
    add but not publish got 「你不能发布」 only after pressing it."""
    index = first_article_index()
    writers = Group.objects.create(name="只写不发216")
    writers.permissions.add(
        Permission.objects.get(
            content_type__app_label="wagtailadmin", codename="access_admin"
        )
    )
    GroupPagePermission.objects.create(
        group=writers,
        page=index,
        permission=Permission.objects.get(
            content_type__app_label="wagtailcore", codename="add_page"
        ),
    )
    # No verified email: a verified one is put in 投稿者 by the system,
    # which may publish (see test_a_manager_without_submission_...).
    add_only = User.objects.create_user(
        email="addonly216@example.com",
        password="Correct-Horse-Battery-1",
        nickname="只写216",
        agreed_terms_at=timezone.now(),
        agreed_cross_border_at=timezone.now(),
    )
    add_only.groups.add(writers)
    assert not add_only.groups.filter(name=GROUP_SUBMITTER).exists()
    client.force_login(add_only)
    page = client.get(reverse("backoffice:article_new"))
    assert page.status_code == 200
    assert 'name="publish"' not in page.content.decode()

    client.force_login(_user("canpublish216@example.com", GROUP_SUBMITTER))
    page = client.get(reverse("backoffice:article_new"))
    assert page.status_code == 200
    assert 'name="publish"' in page.content.decode()


# --- F5: the picture dialog and a lost session --------------------------------


def test_the_picture_dialog_does_not_show_a_redirected_page():
    """216, F5: a lost session answered with the login page, which the
    dialog showed as if it were the upload (a substring guard)."""
    source = _read("static/js/backoffice.js")
    loader = source.split("function load(url, options)", 1)[1]
    loader = loader.split("function choose(", 1)[0]
    # The refusal itself, before the page is read (mutation 216 caught that
    # the bare word also appears in the error's own flag).
    guard = "if (!response.ok || response.redirected) {"
    assert guard in loader
    assert loader.index(guard) < loader.index("response.text()")
    assert "重新登录后再选图片" in loader


# --- F6: the avatar review's way back on HTTPS --------------------------------


@pytest.mark.django_db
def test_the_avatar_review_does_not_go_back_over_http_from_https(site, client):
    """216, F6: on an HTTPS request a plain-HTTP ``next`` is refused, as
    the other three review actions already did."""
    client.force_login(_user("avatar216@example.com", "内容编辑"))
    url = reverse("avatar_review_action", args=[1])
    fallback = reverse("avatar_review")

    insecure = client.post(url, {"next": "http://testserver/admin/"}, secure=True)
    assert insecure.status_code == 302
    assert insecure["Location"] == fallback

    local = client.post(url, {"next": "/admin/x/"}, secure=True)
    assert local["Location"] == "/admin/x/"

    secure = client.post(url, {"next": "https://testserver/admin/"}, secure=True)
    assert secure["Location"] == "https://testserver/admin/"


# --- F7: the picture picker's spoken names ------------------------------------


@pytest.mark.django_db
def test_the_picture_picker_names_its_buttons(site):
    """216, F7: the field's <label> points at a hidden input; a page of
    pictures read out as N times 「选择」. The buttons carry the name."""
    user = _root("picker216@example.com")

    class CoverForm(forms.Form):
        cover = image_field(user, label="封面")

    html = str(CoverForm()["cover"])

    assert 'aria-label="选择封面"' in html
    assert 'aria-label="清除封面"' in html
    assert 'role="group" aria-label="封面"' in html
