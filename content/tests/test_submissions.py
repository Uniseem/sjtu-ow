from io import BytesIO

import pytest
from allauth.account.models import EmailAddress
from django.contrib.auth.models import Group
from django.core.exceptions import ValidationError
from django.core.files.base import ContentFile
from django.core.management import call_command
from django.urls import reverse
from django.utils import timezone
from PIL import Image as PILImage
from wagtail.images.models import Image
from wagtail.models import Collection, GroupCollectionPermission, Site

from accounts.models import Feature, FeatureGroupRestriction, FeatureUserRule, User
from accounts.services import GROUP_CONTENT, GROUP_SUBMITTER
from content.blocks import UNSUPPORTED_VIDEO_MESSAGE, VideoBlock
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
        body=[("paragraph", "<p>正文</p>")],
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
def test_submitter_cannot_publish_and_editor_approval_goes_live(site_ready):
    news = site_ready
    submitter = _verify(_user(email="s@example.com", nickname="投稿甲"))
    editor = _verify(_user(email="e@example.com", nickname="编辑甲"))
    editor.groups.add(Group.objects.get(name=GROUP_CONTENT))
    guide = ArticleCategory.objects.get(slug="guide")
    page = _article(news, guide, submitter, title="待审稿", slug="pending-one")
    assert news.permissions_for_user(submitter).can_add_subpage()
    assert page.permissions_for_user(submitter).can_publish() is False
    workflow = page.get_workflow()
    assert workflow is not None
    workflow.start(page, submitter)
    page.refresh_from_db()
    assert page.live is False
    state = page.current_workflow_state
    assert state is not None
    state.current_task_state.approve(user=editor)
    page.refresh_from_db()
    assert page.live is True


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

    tournaments_page = _follow(client, "/admin/tournaments/")
    assert tournaments_page.status_code == 404

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
def test_submitter_image_collection_and_no_publish_permission(site_ready):
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
    assert page.permissions_for_user(submitter).can_publish() is False


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

    block = VideoBlock()
    with pytest.raises(ValidationError, match="哔哩哔哩"):
        block.clean(block.to_python("https://www.youtube.com/watch?v=dQw4w9WgXcQ"))
    cleaned = block.clean(block.to_python(BV_URL))
    assert cleaned.url == BV_URL
    assert UNSUPPORTED_VIDEO_MESSAGE


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


@pytest.mark.django_db(transaction=True)
def test_workflow_submission_sends_queued_mail(settings):
    from django.core import mail
    from django_tasks_db.models import DBTaskResult

    from core.tasks import deliver_queued_email

    settings.EMAIL_BACKEND = "core.mail.QueuedEmailBackend"
    settings.EMAIL_DELIVERY_BACKEND = "django.core.mail.backends.locmem.EmailBackend"
    call_command("init_site", verbosity=0)
    news = ArticleIndexPage.objects.get(slug="news")
    submitter = _verify(_user(email="mail-s@example.com", nickname="投稿邮"))
    editor = _verify(_user(email="mail-e@example.com", nickname="编辑邮"))
    editor.groups.add(Group.objects.get(name=GROUP_CONTENT))
    guide = ArticleCategory.objects.get(slug="guide")
    page = _article(news, guide, submitter, title="邮件审核稿", slug="mail-moderation")
    page.get_workflow().start(page, submitter)
    mail_tasks = DBTaskResult.objects.filter(task_path__contains="deliver_queued_email")
    assert mail_tasks.exists()
    for row in mail_tasks:
        payload = row.args_kwargs["args"][0]
        deliver_queued_email.call(payload)
    assert mail.outbox
    blob = "\n".join(f"{message.subject}\n{message.body}" for message in mail.outbox)
    assert "邮件审核稿" in blob or "投稿邮" in blob or "编辑邮" in blob


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
