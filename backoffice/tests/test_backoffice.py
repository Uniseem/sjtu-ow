"""Round 196: the back office written for the site (docs/admin.md, v7.0).

The door, Wagtail's admin left to superusers, and each page's rules from
docs/admin-inventory.md, now in the site's own views: articles through
Wagtail's revisions, the site pages, pictures and the picture dialog, saving
a tournament or scrim, users with their roles and rules, roles with their
restrictions, the site settings' secrets and the action log.
"""

import io
import json
import re
from datetime import timedelta
from unittest import mock

import pytest
from django.contrib.auth.models import Group
from django.core.files.uploadedfile import SimpleUploadedFile
from django.core.management import call_command
from django.urls import reverse
from django.utils import timezone
from PIL import Image as PILImage
from wagtail.images import get_image_model
from wagtail.models import Collection

from accounts.models import Feature, FeatureGroupRestriction, FeatureUserRule, User
from accounts.services import GROUP_SUBMITTER
from accounts.tests.test_onboarding import _user
from content.models import (
    ArticleCategory,
    ArticleIndexPage,
    ArticlePage,
    HomePage,
    StandardPage,
)
from content.services import SUBMISSION_IMAGE_COLLECTION
from core.models import SiteSettings
from scrims.models import Scrim, ScrimStatus
from tournaments.models import Tournament, TournamentStatus


@pytest.fixture
def site(db):
    call_command("init_site", verbosity=0)


@pytest.fixture
def media(settings, tmp_path):
    settings.MEDIA_ROOT = tmp_path


def _root(email="root196@example.com"):
    user = _user(email)
    User.objects.filter(pk=user.pk).update(is_superuser=True, is_staff=True)
    return User.objects.get(pk=user.pk)


def _png(name="pic.png", size=(40, 30)):
    buffer = io.BytesIO()
    PILImage.new("RGB", size, (200, 80, 60)).save(buffer, format="PNG")
    return SimpleUploadedFile(name, buffer.getvalue(), content_type="image/png")


def _article(author, title="后台文章196", live=False, **extra):
    news = ArticleIndexPage.objects.get(slug="news")
    page = ArticlePage(
        title=title,
        slug=f"bo-{ArticlePage.objects.count()}",
        category=ArticleCategory.objects.get(slug="guide"),
        author=author,
        owner=author,
        summary="摘要",
        body="正文",
        live=False,
        **extra,
    )
    news.add_child(instance=page)
    revision = page.save_revision(user=author)
    if live:
        revision.publish()
    return ArticlePage.objects.get(pk=page.pk)


# --- the door (docs/admin.md 2) ----------------------------------------------------


@pytest.mark.django_db
def test_the_door(site, client):
    home = reverse("backoffice:home")
    response = client.get(home)
    assert response.status_code == 302 and "/accounts/login/" in response.url
    stranger = User.objects.create_user(
        email="stranger196@example.com",
        password="x",
        nickname="未验证",
        agreed_terms_at=timezone.now(),
        agreed_cross_border_at=timezone.now(),
    )
    client.force_login(stranger)  # no verified email: not a submitter
    assert client.get(home).status_code == 403
    client.force_login(_user("member196@example.com", GROUP_SUBMITTER))
    page = client.get(home)
    assert page.status_code == 200
    assert "no-store" in page["Cache-Control"] or "no-cache" in page["Cache-Control"]


@pytest.mark.django_db
def test_wagtails_own_admin_is_for_superusers(site, client):
    client.force_login(_user("editor196@example.com", "内容编辑"))
    for path in ("/wagtail/", "/wagtail/pages/", "/wagtail/users/"):
        response = client.get(path)
        assert response.status_code == 302 and response["Location"] == "/admin/", path
    client.force_login(_root())
    assert client.get("/wagtail/").status_code == 200
    settings_page = client.get(reverse("backoffice:site_settings")).content.decode()
    assert 'href="/wagtail/"' in settings_page  # the way in, for superusers only
    editor_home = client.get(reverse("backoffice:home")).content.decode()
    assert "Wagtail 底层后台" in editor_home
    client.force_login(_user("editor196b@example.com", "内容编辑"))
    assert (
        "Wagtail 底层后台"
        not in client.get(reverse("backoffice:home")).content.decode()
    )


@pytest.mark.django_db
def test_both_admins_get_the_admin_policy(site, client):
    client.force_login(_root())
    for path in ("/admin/", "/wagtail/"):
        policy = client.get(path)["Content-Security-Policy"]
        assert "'unsafe-inline'" in policy, path


# --- articles (docs/admin.md 4.2) ----------------------------------------------------


@pytest.mark.django_db
def test_a_member_writes_saves_and_publishes(site, client):
    member = _user("writer196@example.com", GROUP_SUBMITTER)
    client.force_login(member)
    guide = ArticleCategory.objects.get(slug="guide")
    data = {
        "title": "我的新文章",
        "category": guide.pk,
        "summary": "",
        "body": "# 正文",
    }
    response = client.post(reverse("backoffice:article_new"), {**data, "save": "1"})
    page = ArticlePage.objects.get(title="我的新文章")
    assert response.url == reverse("backoffice:article_edit", args=[page.pk])
    assert not page.live and page.owner == member and page.author == member
    assert page.slug == "我的新文章"

    edit = reverse("backoffice:article_edit", args=[page.pk])
    client.post(edit, {**data, "body": "改过的正文", "publish": "1"})
    page.refresh_from_db()
    assert page.live and page.body == "改过的正文"
    # A draft over the live one: the page stays as published, the form
    # shows the draft (docs/admin.md 4.2).
    client.post(edit, {**data, "body": "还没发布的改动", "save": "1"})
    page.refresh_from_db()
    assert page.body == "改过的正文" and page.has_unpublished_changes
    assert "还没发布的改动" in client.get(edit).content.decode()
    preview = client.get(reverse("backoffice:article_preview", args=[page.pk]))
    assert "还没发布的改动" in preview.content.decode()


@pytest.mark.django_db
def test_a_member_only_chooses_open_categories_and_sees_their_own(site, client):
    member = _user("plain196@example.com", GROUP_SUBMITTER)
    other = _user("other196@example.com", GROUP_SUBMITTER)
    theirs = _article(other, title="别人的196", live=True)
    client.force_login(member)
    notice = ArticleCategory.objects.get(slug="notice")
    response = client.post(
        reverse("backoffice:article_new"),
        {"title": "公告196", "category": notice.pk, "body": "x", "save": "1"},
    )
    assert (
        response.status_code == 200
        and not ArticlePage.objects.filter(title="公告196").exists()
    )
    listing = client.get(reverse("backoffice:articles")).content.decode()
    assert "别人的196" not in listing
    for name in ("article_edit", "article_preview"):
        url = reverse(f"backoffice:{name}", args=[theirs.pk])
        assert client.get(url).status_code == 403, name
    for name in ("article_unpublish", "article_delete"):
        url = reverse(f"backoffice:{name}", args=[theirs.pk])
        assert client.post(url).status_code == 403, name
    assert ArticlePage.objects.get(pk=theirs.pk).live


@pytest.mark.django_db
def test_editors_see_every_article_set_the_author_and_announce(site, client):
    writer = _user("w196@example.com", GROUP_SUBMITTER)
    page = _article(writer, title="待通知196", live=True)
    editor = _user("e196@example.com", "内容编辑")
    client.force_login(editor)
    listing = client.get(reverse("backoffice:articles")).content.decode()
    assert "待通知196" in listing
    assert reverse("announce", args=["article", page.pk]) in listing
    mine = client.get(reverse("backoffice:articles") + "?mine=1").content.decode()
    assert "待通知196" not in mine
    edit = client.get(reverse("backoffice:article_edit", args=[page.pk])).content
    assert b'name="author"' in edit and b'name="comments_enabled"' in edit


@pytest.mark.django_db
def test_a_taken_down_article_is_a_draft_again_and_can_be_deleted(site, client):
    member = _user("own196@example.com", GROUP_SUBMITTER)
    page = _article(member, title="撤下196", live=True)
    client.force_login(member)
    client.post(reverse("backoffice:article_unpublish", args=[page.pk]))
    assert not ArticlePage.objects.get(pk=page.pk).live
    client.post(reverse("backoffice:article_delete", args=[page.pk]))
    assert not ArticlePage.objects.filter(pk=page.pk).exists()


@pytest.mark.django_db
def test_the_list_filters_by_status(site, client):
    writer = _user("filter196@example.com", GROUP_SUBMITTER)
    _article(writer, title="草稿196")
    _article(writer, title="已发布196", live=True)
    client.force_login(writer)
    drafts = client.get(reverse("backoffice:articles") + "?status=draft").content
    assert "草稿196".encode() in drafts and "已发布196".encode() not in drafts
    live = client.get(reverse("backoffice:articles") + "?status=live").content
    assert "已发布196".encode() in live and "草稿196".encode() not in live


# --- site pages ---------------------------------------------------------------


@pytest.mark.django_db
def test_site_pages_are_for_editors(site, client):
    about = StandardPage.objects.get(slug="about")
    client.force_login(_user("tm196@example.com", "赛事管理员", GROUP_SUBMITTER))
    for url in (
        reverse("backoffice:pages"),
        reverse("backoffice:page_edit", args=[about.pk]),
        reverse("backoffice:home_pins"),
        reverse("backoffice:index_intro"),
    ):
        assert client.get(url).status_code == 403, url
    client.force_login(_user("ed196@example.com", "内容编辑"))
    client.post(
        reverse("backoffice:page_edit", args=[about.pk]),
        {"title": "关于我们", "body": "我们是交大守望先锋社。", "publish": "1"},
    )
    about.refresh_from_db()
    assert about.live and about.body == "我们是交大守望先锋社。"


@pytest.mark.django_db
def test_pins_are_three_published_articles_at_most_once_each(site, client):
    writer = _user("pin196@example.com", GROUP_SUBMITTER)
    first = _article(writer, title="置顶一", live=True)
    second = _article(writer, title="置顶二", live=True)
    draft = _article(writer, title="草稿不能置顶")
    client.force_login(_user("pinner196@example.com", "内容编辑"))
    url = reverse("backoffice:home_pins")
    same = client.post(url, {"article_1": first.pk, "article_2": first.pk})
    assert "同一篇文章只能置顶一次" in same.content.decode()
    drafted = client.post(url, {"article_1": draft.pk})
    assert drafted.status_code == 200  # not a choice
    client.post(url, {"article_1": second.pk, "article_2": first.pk})
    home = HomePage.objects.get()
    pinned = [rel.article_id for rel in home.pinned_articles.order_by("sort_order")]
    assert pinned == [second.pk, first.pk]
    assert not home.has_unpublished_changes  # saved straight to the homepage


@pytest.mark.django_db
def test_the_news_introduction_is_markdown(site, client):
    client.force_login(_user("intro196@example.com", "内容编辑"))
    client.post(reverse("backoffice:index_intro"), {"intro": "**新人**先看攻略"})
    news = ArticleIndexPage.objects.get(slug="news")
    assert news.intro == "**新人**先看攻略"
    html = client.get(news.url).content.decode()
    assert "<strong>新人</strong>先看攻略" in html


def test_the_migration_turns_the_old_introduction_into_markdown():
    from content.legacy_body import from_html

    assert from_html(
        "<p><b>新人</b>先看<a href='https://example.com'>攻略</a></p>"
    ) == ("**新人**先看[攻略](https://example.com)")


# --- categories ---------------------------------------------------------------


@pytest.mark.django_db
def test_a_category_is_added_and_edited(site, client):
    client.force_login(_user("cat196@example.com", "内容编辑"))
    client.post(
        reverse("backoffice:category_new"),
        {"name": "赛后复盘", "slug": "review-196", "sort_order": "3"},
    )
    category = ArticleCategory.objects.get(slug="review-196")
    assert not category.allow_submission  # an unticked box
    client.post(
        reverse("backoffice:category_edit", args=[category.pk]),
        {
            "name": "复盘",
            "slug": "review-196",
            "sort_order": "3",
            "allow_submission": "on",
        },
    )
    category.refresh_from_db()
    assert category.name == "复盘" and category.allow_submission


# --- pictures (docs/admin.md 4.2) ---------------------------------------------


@pytest.mark.django_db
def test_members_upload_into_the_submission_collection_only(site, media, client):
    member = _user("img196@example.com", GROUP_SUBMITTER)
    client.force_login(member)
    upload = client.get(reverse("backoffice:image_upload")).content.decode()
    assert SUBMISSION_IMAGE_COLLECTION in upload
    assert "（根）" not in upload
    collection = Collection.objects.get(name=SUBMISSION_IMAGE_COLLECTION)
    root = Collection.get_first_root_node()
    refused = client.post(
        reverse("backoffice:image_upload"), {"collection": root.pk, "files": [_png()]}
    )
    assert refused.status_code == 200 and not get_image_model().objects.exists()
    client.post(
        reverse("backoffice:image_upload"),
        {"collection": collection.pk, "files": [_png("a.png"), _png("b.png")]},
    )
    images = get_image_model().objects.order_by("title")
    assert [image.title for image in images] == ["a", "b"]
    assert {image.collection_id for image in images} == {collection.pk}
    assert client.get(reverse("backoffice:collections")).status_code == 403


@pytest.mark.django_db
def test_the_dialog_offers_what_one_may_choose_and_takes_an_upload(site, media, client):
    Image = get_image_model()
    hidden = Collection.get_first_root_node().add_child(name="站长私藏196")
    Image.objects.create(title="私藏图", file=_png("secret.png"), collection=hidden)
    member = _user("dialog196@example.com", GROUP_SUBMITTER)
    client.force_login(member)
    dialog = client.get(reverse("backoffice:image_chooser")).content.decode()
    assert "私藏图" not in dialog
    collection = Collection.objects.get(name=SUBMISSION_IMAGE_COLLECTION)
    response = client.post(
        reverse("backoffice:image_chooser_upload"),
        {"collection": collection.pk, "file": _png("new.png")},
    )
    data = json.loads(response.content)
    assert data["title"] == "new" and data["thumb"]
    dialog = client.get(reverse("backoffice:image_chooser")).content.decode()
    assert f'data-pick-image="{data["id"]}"' in dialog
    elsewhere = client.post(
        reverse("backoffice:image_chooser_upload"),
        {"collection": hidden.pk, "file": _png("no.png")},
    )
    assert elsewhere.status_code == 403


@pytest.mark.django_db
def test_a_picture_field_refuses_a_picture_one_may_not_choose(site, media):
    from backoffice.forms import TournamentForm

    Image = get_image_model()
    hidden = Collection.get_first_root_node().add_child(name="站长私藏196b")
    secret = Image.objects.create(title="私藏", file=_png(), collection=hidden)
    manager = _user("pick196@example.com", "赛事管理员", GROUP_SUBMITTER)
    form = TournamentForm(instance=Tournament(), user=manager)
    assert not form.fields["cover"].queryset.filter(pk=secret.pk).exists()
    # Already on the tournament (an editor chose it): it stays a valid choice.
    kept = Tournament(cover=secret)
    form = TournamentForm(instance=kept, user=manager)
    assert form.fields["cover"].queryset.filter(pk=secret.pk).exists()


@pytest.mark.django_db
def test_superusers_arrange_collections(site, client):
    client.force_login(_root())
    root = Collection.get_first_root_node()
    client.post(
        reverse("backoffice:collections"), {"name": "默认封面196", "parent": root.pk}
    )
    made = Collection.objects.get(name="默认封面196")
    client.post(
        reverse("backoffice:collection_rename", args=[made.pk]), {"name": "封面"}
    )
    made.refresh_from_db()
    assert made.name == "封面"
    client.post(reverse("backoffice:collection_delete", args=[root.pk]))
    assert Collection.objects.filter(pk=root.pk).exists()
    client.post(reverse("backoffice:collection_delete", args=[made.pk]))
    assert not Collection.objects.filter(pk=made.pk).exists()


# --- tournaments and scrims (docs/admin.md 4.3) -------------------------------


def _tournament_data(**changes):
    now = timezone.localtime(timezone.now())
    data = {
        "title": "后台杯196",
        "summary": "",
        "description": "",
        "registration_opens_at": f"{now - timedelta(days=1):%Y-%m-%dT%H:%M}",
        "registration_closes_at": f"{now + timedelta(days=6):%Y-%m-%dT%H:%M}",
        "starts_at": f"{now + timedelta(days=8):%Y-%m-%dT%H:%M}",
        "registration_mode": "team",
        "roster_min": "5",
        "roster_max": "6",
        "participant_contact": "",
    }
    data.update(changes)
    return data


@pytest.mark.django_db
def test_saving_a_tournament_does_what_the_admin_did(site, client):
    manager = _user("tour196@example.com", "赛事管理员", GROUP_SUBMITTER)
    client.force_login(manager)
    with mock.patch("tournaments.services.after_change") as after:
        response = client.post(reverse("tournaments:add"), _tournament_data())
    tournament = Tournament.objects.get(title="后台杯196")
    assert response.url == reverse("tournaments:edit", args=[tournament.pk])
    assert tournament.created_by == manager and tournament.status == "draft"
    assert after.call_count == 1
    with mock.patch("tournaments.services.time_changed") as moved:
        client.post(
            reverse("tournaments:edit", args=[tournament.pk]),
            _tournament_data(title="改名杯196"),
        )
    old_start = moved.call_args.args[1]
    assert old_start == tournament.starts_at  # the start before this save


@pytest.mark.django_db
def test_an_untouched_time_with_seconds_is_kept(site, client):
    """The box holds minutes; a stored 19:30:42 must not become 19:30 and
    tell everyone the time changed (backoffice.forms.KeepSeconds)."""
    from tournaments.tests.test_tournaments import _tournament

    start = (timezone.now() + timedelta(days=9)).replace(second=42, microsecond=0)
    tournament = _tournament(starts_at=start, status=TournamentStatus.PUBLISHED)
    client.force_login(_user("sec196@example.com", "赛事管理员", GROUP_SUBMITTER))
    data = _tournament_data(
        title=tournament.title,
        starts_at=f"{timezone.localtime(start):%Y-%m-%dT%H:%M}",
        registration_opens_at=f"{timezone.localtime(tournament.registration_opens_at):%Y-%m-%dT%H:%M}",
        registration_closes_at=f"{timezone.localtime(tournament.registration_closes_at):%Y-%m-%dT%H:%M}",
        roster_min=tournament.roster_min,
        roster_max=tournament.roster_max,
        registration_mode=tournament.registration_mode,
    )
    with mock.patch("tournaments.notifications.time_changed") as letter:
        client.post(reverse("tournaments:edit", args=[tournament.pk]), data)
    tournament.refresh_from_db()
    assert tournament.starts_at == start
    assert letter.call_count == 0


@pytest.mark.django_db
def test_only_a_draft_never_published_is_deleted(site, client):
    from tournaments.tests.test_tournaments import _tournament

    client.force_login(_user("del196@example.com", "赛事管理员", GROUP_SUBMITTER))
    published = _tournament(status=TournamentStatus.PUBLISHED)
    response = client.post(reverse("tournaments:delete", args=[published.pk]))
    assert response.url == reverse("tournaments:edit", args=[published.pk])
    assert Tournament.objects.filter(pk=published.pk).exists()
    draft = _tournament(status=TournamentStatus.DRAFT, published_at=None)
    listing = client.get(reverse("tournaments:index")).content.decode()
    assert reverse("tournaments:delete", args=[draft.pk]) in listing
    assert reverse("tournaments:delete", args=[published.pk]) not in listing
    client.post(reverse("tournaments:delete", args=[draft.pk]))
    assert not Tournament.objects.filter(pk=draft.pk).exists()


@pytest.mark.django_db
def test_a_scrim_is_saved_and_only_an_empty_draft_deleted(site, client):
    from scrims.tests.test_scrims import make_scrim

    manager = _user("scrim196@example.com", "内战管理员", GROUP_SUBMITTER)
    client.force_login(manager)
    now = timezone.localtime(timezone.now())
    with mock.patch("scrims.services.after_change") as after:
        client.post(
            reverse("scrims:add"),
            {
                "title": "周五后台内战",
                "description": "",
                "starts_at": f"{now + timedelta(days=2):%Y-%m-%dT%H:%M}",
                "signup_closes_at": "",
                "format": "rq_5v5",
            },
        )
    scrim = Scrim.objects.get(title="周五后台内战")
    assert scrim.created_by == manager and after.call_count == 1
    published = make_scrim(title="已发布196")
    client.post(reverse("scrims:delete", args=[published.pk]))
    assert Scrim.objects.filter(pk=published.pk).exists()
    assert scrim.status == ScrimStatus.DRAFT
    client.post(reverse("scrims:delete", args=[scrim.pk]))
    assert not Scrim.objects.filter(pk=scrim.pk).exists()


# --- people (docs/admin.md 4.4) -----------------------------------------------


@pytest.mark.django_db
def test_roles_are_ticked_and_system_groups_left_alone(site, client):
    member = _user("role196@example.com", GROUP_SUBMITTER)
    client.force_login(_root())
    url = reverse("backoffice:user_edit", args=[member.pk])
    page = client.get(url).content.decode()
    labels = re.findall(r'name="roles" value="([^"]+)"', page)
    assert labels[:4] == ["内容编辑", "认证作者", "赛事管理员", "内战管理员"]
    assert GROUP_SUBMITTER not in labels and "交大用户" not in labels
    client.post(
        url,
        {"nickname": member.nickname, "is_active": "on", "roles": ["赛事管理员"]},
    )
    names = set(member.groups.values_list("name", flat=True))
    assert "赛事管理员" in names and GROUP_SUBMITTER in names
    client.post(url, {"nickname": member.nickname, "is_active": "on", "roles": []})
    names = set(member.groups.values_list("name", flat=True))
    assert "赛事管理员" not in names and GROUP_SUBMITTER in names


@pytest.mark.django_db
def test_nobody_switches_their_own_account_off(site, client):
    root = _root()
    client.force_login(root)
    url = reverse("backoffice:user_edit", args=[root.pk])
    assert 'name="is_active"' not in client.get(url).content.decode()
    client.post(url, {"nickname": root.nickname, "deactivation_note": "手滑"})
    root.refresh_from_db()
    assert root.is_active


@pytest.mark.django_db
def test_rules_for_one_person_and_for_a_role(site, client):
    member = _user("rule196@example.com", GROUP_SUBMITTER)
    root = _root()
    client.force_login(root)
    add = reverse("backoffice:user_rule_add", args=[member.pk])
    client.post(
        add, {"feature": Feature.TEAM_CREATE, "allowed": "False", "note": "刷队"}
    )
    rule = FeatureUserRule.objects.get(user=member)
    assert not rule.allowed and rule.updated_by == root and rule.note == "刷队"
    again = client.post(
        add, {"feature": Feature.TEAM_CREATE, "allowed": "True"}, follow=True
    )
    assert "已经有单独规则了" in again.content.decode()
    assert FeatureUserRule.objects.filter(user=member).count() == 1
    client.post(reverse("backoffice:user_rule_delete", args=[rule.pk]))
    assert not FeatureUserRule.objects.filter(user=member).exists()

    group = Group.objects.get(name="校外用户")
    restrict = reverse("backoffice:role_restriction_add", args=[group.pk])
    client.post(restrict, {"feature": Feature.TEAM_CREATE, "note": "先不开放"})
    restriction = FeatureGroupRestriction.objects.get(group=group)
    assert restriction.updated_by == root
    twice = client.post(restrict, {"feature": Feature.TEAM_CREATE}, follow=True)
    assert "这一组的这项功能已经关掉了" in twice.content.decode()
    client.post(reverse("backoffice:role_restriction_delete", args=[restriction.pk]))
    assert not FeatureGroupRestriction.objects.filter(group=group).exists()


@pytest.mark.django_db
def test_people_pages_are_for_superusers(site, client):
    member = _user("people196@example.com", GROUP_SUBMITTER)
    client.force_login(_user("editor196c@example.com", "内容编辑"))
    for url in (
        reverse("backoffice:users"),
        reverse("backoffice:user_edit", args=[member.pk]),
        reverse("backoffice:roles"),
        reverse("teams:index"),
    ):
        assert client.get(url).status_code == 403, url
    response = client.post(
        reverse("backoffice:user_rule_add", args=[member.pk]),
        {"feature": Feature.TEAM_CREATE, "allowed": "False"},
    )
    assert response.status_code == 403
    assert not FeatureUserRule.objects.exists()


# --- settings and the log (docs/admin.md 4.6) ---------------------------------


@pytest.mark.django_db
def test_the_secrets_are_never_shown_and_blank_keeps_them(site, client):
    site_settings = SiteSettings.load()
    site_settings.smtp_password = "s3cret-196"
    site_settings.save()
    client.force_login(_root())
    url = reverse("backoffice:site_settings")
    page = client.get(url).content.decode()
    assert "s3cret-196" not in page
    from wagtail.test.utils.form_data import querydict_from_html

    data = querydict_from_html(page, form_index=0)
    data["site_description"] = "交大守望先锋社区"
    response = client.post(url, data)
    assert response.status_code == 302, response.content.decode()[:1500]
    site_settings = SiteSettings.load()
    assert site_settings.smtp_password == "s3cret-196"
    assert site_settings.site_description == "交大守望先锋社区"


@pytest.mark.django_db
def test_the_log_shows_page_and_model_entries_with_their_names(site, client):
    from tournaments.tests.test_tournaments import _tournament

    writer = _user("log196@example.com", GROUP_SUBMITTER)
    _article(writer, title="记录里的文章", live=True)
    manager = _user("logm196@example.com", "赛事管理员", GROUP_SUBMITTER)
    client.force_login(manager)
    tournament = _tournament(status=TournamentStatus.DRAFT, published_at=None)
    client.post(reverse("tournament_action", args=[tournament.pk, "publish"]))
    client.force_login(_root())
    log = client.get(reverse("backoffice:log")).content.decode()
    assert "记录里的文章" in log and tournament.title in log
    assert "发布赛事" in log
    only = client.get(reverse("backoffice:log") + "?action=tournaments.publish")
    assert "记录里的文章" not in only.content.decode()


@pytest.mark.django_db(transaction=True)
def test_the_migration_turns_the_introduction_and_its_drafts_into_markdown():
    """content/0009 (v7.0): the live row and every saved revision."""
    from django.db import connection
    from django.db.migrations.executor import MigrationExecutor

    def migrate(target):
        executor = MigrationExecutor(connection)
        executor.loader.build_graph()
        executor.migrate([target])

    call_command("init_site", verbosity=0)
    migrate(("content", "0008_publish_without_review"))
    news = ArticleIndexPage.objects.get(slug="news")
    news.intro = "<p><b>新人</b>先看<a href='https://example.com'>攻略</a></p>"
    news.save()
    revision = news.save_revision()
    migrate(("content", "0009_markdown_intro"))
    news.refresh_from_db()
    revision.refresh_from_db()
    assert news.intro == "**新人**先看[攻略](https://example.com)"
    assert revision.content["intro"] == "**新人**先看[攻略](https://example.com)"


@pytest.mark.django_db
def test_the_ways_in_lead_to_the_back_office(site, client):
    from content.services import article_create_admin_url

    assert article_create_admin_url() == reverse("backoffice:article_new")
    robots = client.get("/robots.txt").content.decode()
    assert "Disallow: /wagtail/" in robots


def test_caddy_always_hands_both_admins_to_django():
    """Neither is prerendered; a stale file under prerendered/ must never
    answer for them (deploy/Caddyfile)."""
    from django.conf import settings

    caddyfile = (settings.BASE_DIR / "deploy" / "Caddyfile").read_text(encoding="utf-8")
    line = next(row for row in caddyfile.splitlines() if "@always_django path" in row)
    for path in ("/admin/*", "/admin", "/wagtail/*", "/wagtail"):
        assert f" {path} " in f" {line} ", path
