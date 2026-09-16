"""Idempotent site bootstrap for categories, page tree, workflows, and media."""

from __future__ import annotations

from urllib.parse import urlparse

from django.conf import settings
from django.contrib.auth.models import Group, Permission
from wagtail.coreutils import get_supported_content_language_variant
from wagtail.models import (
    Collection,
    GroupApprovalTask,
    GroupCollectionPermission,
    GroupPagePermission,
    Locale,
    Page,
    Site,
    Workflow,
    WorkflowPage,
    WorkflowTask,
)

from accounts.services import GROUP_AUTHOR, GROUP_CONTENT, GROUP_SUBMITTER
from content.models import ArticleCategory, ArticleIndexPage, HomePage, StandardPage

INITIAL_CATEGORIES = (
    ("notice", "公告", False, 10),
    ("event-notice", "赛事通知", False, 20),
    ("guide", "攻略", True, 30),
    ("match-report", "战报", True, 40),
    ("experience", "心得", True, 50),
)

WAGTAIL_STOCK_GROUP_NAMES = ("Editors", "Moderators")

SITE_DISPLAY_NAME = "上海交通大学守望先锋社区"

STANDARD_PAGES = (
    ("用户协议", "terms"),
    ("隐私政策", "privacy"),
    ("关于我们", "about"),
)

SUBMISSION_IMAGE_COLLECTION = "投稿图片"
CONTENT_WORKFLOW_NAME = "内容审核"
CONTENT_WORKFLOW_TASK_NAME = "内容编辑审核"


def parse_site_url(url: str) -> tuple[str, int]:
    """Hostname and port from SITE_URL (https→443, http→80, else given port)."""
    parsed = urlparse(url or "")
    hostname = (parsed.hostname or "localhost").lower()
    if parsed.port:
        port = parsed.port
    elif (parsed.scheme or "").lower() == "https":
        port = 443
    else:
        port = 80
    return hostname, port


def sync_default_site_from_site_url(site: Site | None = None) -> Site:
    """Set the default Wagtail Site hostname/port from SITE_URL every run."""
    hostname, port = parse_site_url(settings.SITE_URL)
    if site is None:
        site = Site.objects.filter(is_default_site=True).first()
    if site is None:
        raise Site.DoesNotExist("Default Wagtail site is missing.")
    dirty = False
    if site.hostname != hostname:
        site.hostname = hostname
        dirty = True
    if site.port != port:
        site.port = port
        dirty = True
    if dirty:
        site.save()
    return site


def ensure_article_categories() -> list[ArticleCategory]:
    """Create the five default categories. Existing rows are left unchanged."""
    categories = []
    for slug, name, allow_submission, sort_order in INITIAL_CATEGORIES:
        category, _created = ArticleCategory.objects.get_or_create(
            slug=slug,
            defaults={
                "name": name,
                "allow_submission": allow_submission,
                "sort_order": sort_order,
            },
        )
        categories.append(category)
    return categories


def remove_wagtail_stock_groups() -> list[str]:
    """Delete Wagtail's unused Editors/Moderators groups.

    This site uses the Chinese preset group「内容编辑」. The English stock
    groups have no members or extra permissions on a fresh install and only
    confuse the group list.
    """
    names = list(
        Group.objects.filter(name__in=WAGTAIL_STOCK_GROUP_NAMES).values_list(
            "name", flat=True
        )
    )
    if names:
        Group.objects.filter(name__in=WAGTAIL_STOCK_GROUP_NAMES).delete()
    return names


def _default_locale() -> Locale:
    locale = Locale.objects.first()
    if locale is None:
        locale = Locale.objects.create(
            language_code=get_supported_content_language_variant(settings.LANGUAGE_CODE)
        )
    return locale


def _ensure_root() -> Page:
    root = Page.get_first_root_node()
    if root is not None:
        return root
    return Page.add_root(title="Root", slug="root", locale=_default_locale())


def _ensure_child(parent: Page, model, title: str, slug: str, **fields):
    existing = parent.get_children().type(model).filter(slug=slug).first()
    if existing:
        return existing.specific
    page = model(title=title, slug=slug, **fields)
    parent.add_child(instance=page)
    page.save_revision().publish()
    return page


def _delete_stock_welcome(root: Page, homepage: HomePage) -> None:
    for sibling in root.get_children().exclude(pk=homepage.pk):
        if sibling.specific_class is Page:
            sibling.delete()


def ensure_page_tree() -> HomePage:
    """Create homepage, 资讯, terms/privacy/about. Safe to run repeatedly."""
    root = _ensure_root()
    homepage = HomePage.objects.filter(depth=2).first()
    if homepage is None:
        # Wagtail's welcome page already uses slug ``home``; create beside it.
        homepage = HomePage(title="首页", slug="sjtu-home")
        root.add_child(instance=homepage)
        homepage.save_revision().publish()
    elif not homepage.live:
        homepage.save_revision().publish()

    hostname, port = parse_site_url(settings.SITE_URL)
    site = Site.objects.filter(is_default_site=True).first()
    if site is None:
        site = Site.objects.create(
            hostname=hostname,
            port=port,
            root_page=homepage,
            is_default_site=True,
            site_name=SITE_DISPLAY_NAME,
        )
    else:
        dirty = False
        if site.root_page_id != homepage.id:
            site.root_page = homepage
            dirty = True
        if not site.site_name:
            site.site_name = SITE_DISPLAY_NAME
            dirty = True
        if dirty:
            site.save()
        sync_default_site_from_site_url(site)

    _delete_stock_welcome(root, homepage)
    if homepage.slug != "home":
        homepage.slug = "home"
        homepage.save()

    _ensure_child(homepage, ArticleIndexPage, "资讯", "news", intro="")
    for title, slug in STANDARD_PAGES:
        _ensure_child(homepage, StandardPage, title, slug, body=[])
    return homepage


def first_article_index() -> ArticleIndexPage | None:
    return ArticleIndexPage.objects.order_by("path").first()


def article_create_admin_url() -> str | None:
    from django.urls import reverse

    index = first_article_index()
    if index is None:
        return None
    return reverse(
        "wagtailadmin_pages:add",
        args=["content", "articlepage", index.pk],
    )


def _page_permission(codename: str) -> Permission:
    return Permission.objects.get(
        content_type__app_label="wagtailcore",
        codename=codename,
    )


def _image_permission(codename: str) -> Permission:
    return Permission.objects.get(
        content_type__app_label="wagtailimages",
        codename=codename,
    )


def _grant_page_perms(group: Group, page: Page, codenames: tuple[str, ...]) -> None:
    for codename in codenames:
        GroupPagePermission.objects.get_or_create(
            group=group,
            page=page,
            permission=_page_permission(codename),
        )


def _grant_collection_perms(
    group: Group, collection: Collection, codenames: tuple[str, ...]
) -> None:
    for codename in codenames:
        GroupCollectionPermission.objects.get_or_create(
            group=group,
            collection=collection,
            permission=_image_permission(codename),
        )


def ensure_submission_image_collection() -> Collection:
    root = Collection.get_first_root_node()
    if root is None:
        root = Collection.add_root(name="Root")
    existing = root.get_children().filter(name=SUBMISSION_IMAGE_COLLECTION).first()
    if existing is not None:
        return existing
    return root.add_child(name=SUBMISSION_IMAGE_COLLECTION)


def ensure_content_workflow() -> Workflow:
    workflow, _created = Workflow.objects.get_or_create(
        name=CONTENT_WORKFLOW_NAME,
        defaults={"active": True},
    )
    if not workflow.active:
        workflow.active = True
        workflow.save(update_fields=["active"])

    task = GroupApprovalTask.objects.filter(name=CONTENT_WORKFLOW_TASK_NAME).first()
    if task is None:
        task = GroupApprovalTask.objects.create(
            name=CONTENT_WORKFLOW_TASK_NAME,
            active=True,
        )
    elif not task.active:
        task.active = True
        task.save(update_fields=["active"])

    content_group, _ = Group.objects.get_or_create(name=GROUP_CONTENT)
    task.groups.add(content_group)
    WorkflowTask.objects.get_or_create(
        workflow=workflow,
        task=task,
        defaults={"sort_order": 0},
    )
    for index in ArticleIndexPage.objects.all():
        WorkflowPage.objects.update_or_create(
            page=index,
            defaults={"workflow": workflow},
        )
    return workflow


def assign_content_permissions() -> None:
    """Page and collection permissions for 内容编辑 / 认证作者 / 投稿者."""
    groups = {
        name: Group.objects.get_or_create(name=name)[0]
        for name in (GROUP_CONTENT, GROUP_AUTHOR, GROUP_SUBMITTER)
    }
    homepage = HomePage.objects.filter(depth=2).first()
    if homepage is not None:
        _grant_page_perms(
            groups[GROUP_CONTENT],
            homepage,
            ("add_page", "change_page", "publish_page", "lock_page", "unlock_page"),
        )
    for index in ArticleIndexPage.objects.all():
        _grant_page_perms(groups[GROUP_SUBMITTER], index, ("add_page",))
        _grant_page_perms(
            groups[GROUP_AUTHOR],
            index,
            ("add_page", "publish_page"),
        )
        _grant_page_perms(
            groups[GROUP_CONTENT],
            index,
            ("add_page", "change_page", "publish_page", "lock_page", "unlock_page"),
        )

    collection = ensure_submission_image_collection()
    _grant_collection_perms(
        groups[GROUP_SUBMITTER],
        collection,
        ("add_image", "choose_image"),
    )
    _grant_collection_perms(
        groups[GROUP_AUTHOR],
        collection,
        ("add_image", "choose_image"),
    )
    root = Collection.get_first_root_node()
    if root is not None:
        _grant_collection_perms(
            groups[GROUP_CONTENT],
            root,
            ("add_image", "change_image", "choose_image", "delete_image"),
        )
