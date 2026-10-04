from io import BytesIO

import pytest
from allauth.account.models import EmailAddress
from django.contrib.auth.models import Group
from django.core.files.base import ContentFile
from django.core.management import call_command
from django.urls import reverse
from django.utils import timezone
from PIL import Image as PILImage
from wagtail.embeds.exceptions import EmbedNotFoundException
from wagtail.images.models import Image
from wagtail.models import Collection, GroupCollectionPermission, Site

from accounts.models import Feature, FeatureGroupRestriction, FeatureUserRule, User
from accounts.services import GROUP_CONTENT, GROUP_SUBMITTER
from content.embeds import BilibiliEmbedFinder
from content.models import ArticleCategory, ArticleIndexPage, ArticlePage
from content.permissions import is_submitter_only
from content.services import SUBMISSION_IMAGE_COLLECTION, article_create_admin_url

VALID_PASSWORD = "Correct-Horse-Battery-1"
BV_URL = "https://www.bilibili.com/video/BV1xx411c7mD"


def _follow(client, url):
    return client.get(url, follow=True)


def _user(email="player@example.com", nickname="投稿同学", **kwargs):
    kwargs.setdefault("password", VALID_PASSWORD)
    kwargs.setdefault("agreed_terms_at", timezone.now())
    kwargs.setdefault("agreed_cross_border_at", timezone.now())
    return User.objects.create_user(email=email, nickname=nickname, **kwargs)


def _verify(user):
    EmailAddress.objects.update_or_create(
        user=user,
        email=user.email,
        defaults={"verified": True, "primary": True},
    )
    user.refresh_from_db()
    return user


def _image(title="cover"):
    collection = Collection.get_first_root_node()
    if collection is None:
        collection = Collection.add_root(name="Root")
    buffer = BytesIO()
    PILImage.new("RGB", (400, 300), color=(12, 48, 96)).save(buffer, format="PNG")
    image = Image(
        title=title,
        width=400,
        height=300,
        collection=collection,
        file=ContentFile(buffer.getvalue(), name=f"{title}.png"),
    )
    image.save()
    return image


def _article(parent, category, author, *, title, slug, live=False):
    page = ArticlePage(
        title=title,
        slug=slug,
        category=category,
        author=author,
        owner=author,
        summary="摘要",
        body="正文",
    )
    parent.add_child(instance=page)
    if live:
        page.save_revision().publish()
    else:
        page.save_revision(user=author)
        page.unpublish()
    return ArticlePage.objects.get(pk=page.pk)


@pytest.fixture
def site_ready():
    call_command("init_site", verbosity=0)
    return ArticleIndexPage.objects.get(slug="news")


@pytest.mark.django_db
def test_submitter_added_on_email_verify_and_removed_on_deactivate(site_ready):
    user = _user()
    assert GROUP_SUBMITTER not in user.groups.values_list("name", flat=True)
    _verify(user)
    assert GROUP_SUBMITTER in set(user.groups.values_list("name", flat=True))
    user.is_active = False
    user.save()
    assert GROUP_SUBMITTER not in set(user.groups.values_list("name", flat=True))


@pytest.mark.django_db
def test_submitter_removed_by_group_restriction_and_user_rule(site_ready):
    user = _user(is_sjtu=True)
    _verify(user)
    assert GROUP_SUBMITTER in set(user.groups.values_list("name", flat=True))

    sjtu = Group.objects.get(name="交大用户")
    FeatureGroupRestriction.objects.create(
        group=sjtu,
        feature=Feature.ARTICLE_SUBMIT,
        note="暂停交大投稿",
    )
    user.refresh_from_db()
    assert GROUP_SUBMITTER not in set(user.groups.values_list("name", flat=True))

    FeatureGroupRestriction.objects.filter(feature=Feature.ARTICLE_SUBMIT).delete()
    user.refresh_from_db()
    assert GROUP_SUBMITTER in set(user.groups.values_list("name", flat=True))

    FeatureUserRule.objects.create(
        user=user,
        feature=Feature.ARTICLE_SUBMIT,
        allowed=False,
        note="单独禁止",
    )
    user.refresh_from_db()
    assert GROUP_SUBMITTER not in set(user.groups.values_list("name", flat=True))


@pytest.mark.django_db
def test_submitter_resyncs_when_user_changes_group(site_ready):
    user = _user(is_sjtu=False)
    _verify(user)
    external = Group.objects.get(name="校外用户")
    FeatureGroupRestriction.objects.create(
        group=external,
        feature=Feature.ARTICLE_SUBMIT,
        note="校外暂停",
    )
    user.refresh_from_db()
    assert GROUP_SUBMITTER not in set(user.groups.values_list("name", flat=True))
    user.is_sjtu = True
    user.save()
    user.refresh_from_db()
    assert GROUP_SUBMITTER in set(user.groups.values_list("name", flat=True))


@pytest.mark.django_db
def test_submit_entry_shows_reasons_then_redirects(client, site_ready):
    response = client.get(reverse("submit"))
    assert response.status_code == 200
    html = response.content.decode("utf-8")
    assert "未登录" in html
    assert reverse("account_login") in html

    user = _user()
    client.force_login(user)
    blocked = client.get(reverse("submit"))
    assert blocked.status_code == 200
    assert "邮箱未验证" in blocked.content.decode("utf-8")

    _verify(user)
    allowed = client.get(reverse("submit"))
    assert allowed.status_code == 302
    assert allowed["Location"] == article_create_admin_url()


@pytest.mark.django_db
def test_members_publish_their_own_articles_straight_away(client, site_ready):
    """v6.73 (round 195): everyone is trusted; no 内容审核 workflow."""
    news = site_ready
    submitter = _verify(_user(email="s@example.com", nickname="投稿甲"))
    guide = ArticleCategory.objects.get(slug="guide")
    page = _article(news, guide, submitter, title="直接发布", slug="straight-out")
    assert page.get_workflow() is None
    assert page.permissions_for_user(submitter).can_publish()
    client.force_login(submitter)
    client.post(
        reverse("wagtailadmin_pages:edit", args=[page.pk]),
        {
            "title": "直接发布",
            "category": guide.pk,
            "summary": "摘要",
            "body": "正文",
            "action-publish": "action-publish",
        },
    )
    page.refresh_from_db()
    assert page.live is True
    assert page.permissions_for_user(submitter).can_unpublish()


@pytest.mark.django_db
def test_nobody_takes_down_someone_elses_article_but_editors(client, site_ready):
    """Wagtail gives 发布 for the whole section and does not ask whose page
    it is; the article's tester does (v6.73). Verified authors could take
    down anyone's article before."""
    from accounts.services import GROUP_AUTHOR

    news = site_ready
    owner = _verify(_user(email="own195@example.com", nickname="作者195"))
    guide = ArticleCategory.objects.get(slug="guide")
    page = _article(news, guide, owner, title="别人的文章", slug="theirs", live=True)
    member = _verify(_user(email="member195@example.com", nickname="成员195"))
    author = _verify(_user(email="author195@example.com", nickname="认证195"))
    author.groups.add(Group.objects.get(name=GROUP_AUTHOR))
    editor = _verify(_user(email="editor195@example.com", nickname="编辑195"))
    editor.groups.add(Group.objects.get(name=GROUP_CONTENT))

    for other in (member, author):
        tester = page.permissions_for_user(User.objects.get(pk=other.pk))
        assert not tester.can_unpublish() and not tester.can_publish()
        client.force_login(other)
        client.post(reverse("wagtailadmin_pages:unpublish", args=[page.pk]))
        page.refresh_from_db()
        assert page.live, other.nickname
    # Through a plain Page, as the explorer and bulk actions see it.
    from wagtail.models import Page

    plain = Page.objects.get(pk=page.pk)
    assert not plain.permissions_for_user(member).can_unpublish()

    client.force_login(editor)
    client.post(reverse("wagtailadmin_pages:unpublish", args=[page.pk]))
    page.refresh_from_db()
    assert not page.live


@pytest.mark.django_db
def test_init_site_retires_the_review_workflow_left_from_before(site_ready):
    """A database from before v6.73 (or restored from one): init_site takes
    the 内容审核 workflow off the sections and cancels reviews in progress."""
    from wagtail.models import (
        GroupApprovalTask,
        Workflow,
        WorkflowPage,
        WorkflowState,
        WorkflowTask,
    )

    from content.services import retire_content_workflow

    news = site_ready
    workflow = Workflow.objects.create(name="内容审核", active=True)
    task = GroupApprovalTask.objects.create(name="内容编辑审核", active=True)
    task.groups.add(Group.objects.get(name=GROUP_CONTENT))
    WorkflowTask.objects.create(workflow=workflow, task=task, sort_order=0)
    WorkflowPage.objects.create(page=news, workflow=workflow)
    submitter = _verify(_user(email="old195@example.com", nickname="旧稿"))
    guide = ArticleCategory.objects.get(slug="guide")
    page = _article(news, guide, submitter, title="审核中的稿", slug="in-review")
    workflow.start(page, submitter)
    assert page.workflow_in_progress

    call_command("init_site", verbosity=0)
    workflow.refresh_from_db()
    assert not workflow.active
    assert not GroupApprovalTask.objects.get(pk=task.pk).active
    assert not WorkflowPage.objects.filter(page=news).exists()
    assert not WorkflowState.objects.filter(status="in_progress").exists()
    page.refresh_from_db()
    assert not page.live and page.get_workflow() is None
    assert retire_content_workflow() is False  # nothing left to do


@pytest.mark.django_db
def test_submitter_category_and_author_fields(site_ready):
    submitter = _verify(_user(email="s2@example.com"))
    editor = _verify(_user(email="e2@example.com", nickname="编辑乙"))
    editor.groups.add(Group.objects.get(name=GROUP_CONTENT))
    form_class = ArticlePage.get_edit_handler().get_form_class()
    news = site_ready
    submitter_form = form_class(
        instance=ArticlePage(owner=submitter),
        parent_page=news,
        for_user=submitter,
    )
    assert "author" not in submitter_form.fields
    slugs = set(
        submitter_form.fields["category"].queryset.values_list("slug", flat=True)
    )
    assert "notice" not in slugs
    assert "guide" in slugs

    editor_form = form_class(
        instance=ArticlePage(owner=editor),
        parent_page=news,
        for_user=editor,
    )
    assert "author" in editor_form.fields
    editor_slugs = set(
        editor_form.fields["category"].queryset.values_list("slug", flat=True)
    )
    assert "notice" in editor_slugs


@pytest.mark.django_db
def test_submitter_admin_menu_and_restricted_urls(client, site_ready):
    submitter = _verify(_user(email="menu@example.com"))
    assert is_submitter_only(submitter)
    client.force_login(submitter)

    home = client.get(reverse("wagtailadmin_home"))
    assert home.status_code == 200
    html = home.content.decode("utf-8")
    assert "我的投稿" in html
    assert "新建投稿" in html
    assert "w-summary" not in html
    assert "功能权限" not in html
    assert 'name="settings"' not in html
    assert 'name="users"' not in html

    pages = client.get("/admin/pages/")
    assert pages.status_code in {200, 302}

    settings_page = _follow(
        client, reverse("wagtailsettings:edit", args=["core", "sitesettings"])
    )
    assert "SMTP 服务器" not in settings_page.content.decode("utf-8")
    assert settings_page.redirect_chain

    users_page = _follow(client, "/admin/users/")
    assert users_page.redirect_chain

    feature_page = _follow(client, reverse("feature_group_restrictions:index"))
    assert feature_page.redirect_chain

    # The tournaments admin exists since M4; a submitter must be bounced out.
    tournaments_page = _follow(client, "/admin/tournaments/")
    assert tournaments_page.redirect_chain

    images = client.get(reverse("wagtailimages:index"))
    assert images.status_code == 200


@pytest.mark.django_db
def test_submitter_explorer_shows_live_and_own_only(client, site_ready):
    news = site_ready
    owner = _verify(_user(email="own@example.com", nickname="稿件主人"))
    other = _verify(_user(email="other@example.com", nickname="别人"))
    guide = ArticleCategory.objects.get(slug="guide")
    own_draft = _article(news, guide, owner, title="我的草稿", slug="mine-draft")
    other_draft = _article(news, guide, other, title="别人草稿", slug="other-draft")
    live = _article(
        news, guide, other, title="已发布别人", slug="other-live", live=True
    )

    client.force_login(owner)
    listing = client.get(reverse("wagtailadmin_explore", args=[news.pk]))
    assert listing.status_code == 200
    body = listing.content.decode("utf-8")
    assert "我的草稿" in body
    assert "已发布别人" in body
    assert "别人草稿" not in body
    _ = (own_draft.pk, other_draft.pk, live.pk)


@pytest.mark.django_db
def test_submitter_image_collection_and_publish_permission(site_ready):
    submitter = _verify(_user(email="img@example.com"))
    collection = Collection.objects.get(name=SUBMISSION_IMAGE_COLLECTION)
    perms = GroupCollectionPermission.objects.filter(
        group__name=GROUP_SUBMITTER,
        collection=collection,
    )
    codenames = set(perms.values_list("permission__codename", flat=True))
    assert "add_image" in codenames
    assert "choose_image" in codenames
    news = site_ready
    guide = ArticleCategory.objects.get(slug="guide")
    page = _article(news, guide, submitter, title="权限页", slug="perm-page")
    assert page.permissions_for_user(submitter).can_publish()  # v6.73


@pytest.mark.django_db
def test_bilibili_finder_and_unsupported_url_error():
    finder = BilibiliEmbedFinder()
    long_url = BV_URL
    assert finder.accept(long_url)
    result = finder.find_embed(long_url)
    assert "player.bilibili.com/player.html?bvid=BV1xx411c7mD" in result["html"]

    class FakeResp:
        def geturl(self):
            return "https://www.bilibili.com/video/BV1xx411c7mD?p=2"

        def __enter__(self):
            return self

        def __exit__(self, *args):
            return False

    from content import embeds as embed_mod

    original = embed_mod.urlopen
    embed_mod.urlopen = lambda *args, **kwargs: FakeResp()
    try:
        short = "https://b23.tv/abcdef"
        assert finder.accept(short)
        short_result = finder.find_embed(short)
        assert "bvid=BV1xx411c7mD" in short_result["html"]
        assert "page=2" in short_result["html"]
    finally:
        embed_mod.urlopen = original

    # v6.70: a Bilibili link alone on a line is the player; others stay links.
    from content.markdown import render

    assert "player.bilibili.com/player.html?bvid=BV1xx411c7mD" in render(BV_URL)
    youtube = str(render("https://www.youtube.com/watch?v=dQw4w9WgXcQ"))
    assert "<iframe" not in youtube and '<a href="https://www.youtube.com/' in youtube


@pytest.mark.django_db
def test_frame_src_is_bilibili_only():
    from django.conf import settings

    frame_src = [str(item) for item in settings.SECURE_CSP["frame-src"]]
    blob = " ".join(frame_src).lower()
    assert "player.bilibili.com" in blob
    assert "youtube" not in blob
    assert "vimeo" not in blob


@pytest.mark.django_db
def test_image_upload_limits():
    from django.conf import settings
    from wagtail.images.utils import get_allowed_image_extensions

    assert settings.WAGTAILIMAGES_MAX_UPLOAD_SIZE == 5 * 1024 * 1024
    assert set(get_allowed_image_extensions()) == {"jpg", "jpeg", "png", "webp"}


@pytest.mark.django_db
def test_site_hostname_sync_says_when_there_is_no_site():
    """Round 179: run from a shell after changing SITE_URL (README)."""
    from content.services import sync_default_site_from_site_url

    Site.objects.all().delete()
    with pytest.raises(Site.DoesNotExist, match="missing"):
        sync_default_site_from_site_url()


@pytest.mark.django_db
def test_site_hostname_sync_updates_canonical(client, settings):
    call_command("init_site", verbosity=0)
    settings.SITE_URL = "https://ow.example.com"
    call_command("init_site", verbosity=0)
    site = Site.objects.get(is_default_site=True)
    assert site.hostname == "ow.example.com"
    assert site.port == 443

    news = ArticleIndexPage.objects.get(slug="news")
    author = _verify(_user(email="canon@example.com", nickname="作者"))
    guide = ArticleCategory.objects.get(slug="guide")
    article = _article(
        news,
        guide,
        author,
        title="规范网址",
        slug="canonical-one",
        live=True,
    )
    full = article.get_full_url()
    assert full.startswith("https://ow.example.com/")
    response = client.get(article.url)
    html = response.content.decode("utf-8")
    assert 'rel="canonical" href="https://ow.example.com' in html
    assert 'property="og:url" content="https://ow.example.com' in html


def test_bilibili_finder_refuses_a_page_without_a_video_id():
    with pytest.raises(EmbedNotFoundException):
        BilibiliEmbedFinder().find_embed("https://www.bilibili.com/video/")


def test_bilibili_finder_refuses_a_short_link_that_leaves_bilibili(monkeypatch):
    """Design 5.2: Bilibili only, even when the target URL carries a BV id."""
    from content import embeds

    monkeypatch.setattr(
        embeds,
        "follow_b23",
        lambda _url: "https://evil.example.com/video/BV1xx411c7mD",
    )
    with pytest.raises(EmbedNotFoundException):
        BilibiliEmbedFinder().find_embed("https://b23.tv/abcdef")
