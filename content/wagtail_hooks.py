"""Article category snippet, submitter admin chrome, and page explorer filter."""

from django.db.models import Q
from django.urls import reverse
from django.utils.functional import cached_property
from wagtail import hooks
from wagtail.admin.menu import MenuItem
from wagtail.admin.ui.components import Component
from wagtail.admin.ui.menus.pages import PageMenuItem
from wagtail.admin.ui.tables import BooleanColumn
from wagtail.models import WorkflowState
from wagtail.permission_policies.pages import PagePermissionPolicy
from wagtail.snippets.models import register_snippet
from wagtail.snippets.views.snippets import SnippetViewSet

from content.models import ArticleCategory, ArticlePage
from content.permissions import is_submitter_only, sees_only_own_drafts
from content.services import article_create_admin_url

SUBMITTER_MENU_ALLOWLIST = frozenset({"images", "home"})


class ArticleCategoryViewSet(SnippetViewSet):
    model = ArticleCategory
    icon = "tag"
    menu_label = "文章分类"
    menu_name = "article_categories"
    menu_order = 330
    add_to_admin_menu = True
    list_display = [
        "name",
        "slug",
        "sort_order",
        BooleanColumn(
            "allow_submission", label="开放投稿", sort_key="allow_submission"
        ),
    ]
    search_fields = ["name", "slug"]
    ordering = ["sort_order", "name"]
    copy_view_enabled = False


register_snippet(ArticleCategoryViewSet)


class SubmitterHomePanel(Component):
    name = "submitter_home"
    template_name = "content/admin/submitter_home.html"
    order = 50

    def get_context_data(self, parent_context):
        request = parent_context["request"]
        pages = (
            ArticlePage.objects.filter(owner=request.user)
            .select_related("category")
            # One query for every row's review state (round 119).
            .prefetch_workflow_states()
            .order_by("-latest_revision_created_at", "-path")
        )
        rows = []
        for page in pages:
            workflow_state = page.current_workflow_state
            if page.live:
                status = "已发布"
            elif (
                workflow_state is not None
                and workflow_state.status == WorkflowState.STATUS_IN_PROGRESS
            ):
                status = "审核中"
            elif (
                workflow_state is not None
                and workflow_state.status == WorkflowState.STATUS_NEEDS_CHANGES
            ):
                status = "需修改"
            else:
                status = "草稿"
            rows.append(
                {
                    "title": page.get_admin_display_title(),
                    "status": status,
                    "edit_url": reverse("wagtailadmin_pages:edit", args=[page.pk]),
                }
            )
        return {
            "request": request,
            "rows": rows,
            "create_url": article_create_admin_url() or reverse("wagtailadmin_home"),
        }


@hooks.register("construct_main_menu", order=1000)
def filter_submitter_main_menu(request, menu_items):
    if not is_submitter_only(request.user):
        return
    kept = [
        item
        for item in menu_items
        if getattr(item, "name", "") in SUBMITTER_MENU_ALLOWLIST
    ]
    if not any(getattr(item, "name", "") == "home" for item in kept):
        kept.insert(
            0,
            MenuItem(
                "后台首页",
                reverse("wagtailadmin_home"),
                name="home",
                icon_name="home",
                order=1,
            ),
        )
    menu_items[:] = kept


@hooks.register("construct_homepage_panels", order=1000)
def submitter_homepage_panels(request, panels):
    if not is_submitter_only(request.user):
        return
    panels[:] = [SubmitterHomePanel()]


@hooks.register("construct_homepage_summary_items", order=1000)
def hide_summary_for_submitters(request, items):
    if is_submitter_only(request.user):
        items.clear()


@hooks.register("construct_explorer_page_queryset")
def filter_submitter_explorer(parent_page, pages, request):
    if not sees_only_own_drafts(request.user):
        return pages
    return pages.filter(Q(live=True) | Q(owner=request.user))


_original_explorable_instances = PagePermissionPolicy.explorable_instances


def _explorable_instances_for_submitters(self, user):
    pages = _original_explorable_instances(self, user)
    if sees_only_own_drafts(user):
        return pages.filter(Q(live=True) | Q(owner=user))
    return pages


PagePermissionPolicy.explorable_instances = _explorable_instances_for_submitters


class AnnounceArticleItem(PageMenuItem):
    """「通知全体成员」 for a published article (design 10.4, v6.23)."""

    label = "通知全体成员"
    icon_name = "mail"
    priority = 55

    @cached_property
    def url(self):
        return reverse("announce", args=["article", self.page.pk])


def _announce_item(page, user, next_url=None):
    from content.permissions import user_can_edit_author
    from core.services import sent_broadcast

    page_class = page.specific_class or type(page)
    if not (issubclass(page_class, ArticlePage) and page.live):
        return None
    if not user_can_edit_author(user) or sent_broadcast("article", page):
        return None
    return AnnounceArticleItem(page=page, next_url=next_url)


@hooks.register("register_page_listing_more_buttons")
def article_announce_listing_button(page, user, next_url=None):
    item = _announce_item(page, user, next_url)
    if item is not None:
        yield item


@hooks.register("register_page_header_buttons")
def article_announce_header_button(page, user, view_name, next_url=None):
    item = _announce_item(page, user, next_url)
    if item is not None:
        yield item
