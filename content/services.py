"""Idempotent site bootstrap for categories, page tree, and stock groups."""

from django.conf import settings
from django.contrib.auth.models import Group
from wagtail.coreutils import get_supported_content_language_variant
from wagtail.models import Locale, Page, Site

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

    site = Site.objects.filter(is_default_site=True).first()
    if site is None:
        site = Site.objects.create(
            hostname="localhost",
            port=80,
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

    _delete_stock_welcome(root, homepage)
    if homepage.slug != "home":
        homepage.slug = "home"
        homepage.save()

    _ensure_child(homepage, ArticleIndexPage, "资讯", "news", intro="")
    for title, slug in STANDARD_PAGES:
        _ensure_child(homepage, StandardPage, title, slug, body=[])
    return homepage
