"""The admin's first page and its menu (design 14.1, v6.67, round 189).

``WelcomePanel`` says hello and offers the actions this person does most.
``arrange_main_menu`` and ``arrange_settings_menu`` put the sidebar in the
order of the work: the frequent things on the first level, Wagtail's entries
the club has no use for left out (they still open by address).
"""

from __future__ import annotations

from dataclasses import dataclass

from django.urls import reverse
from wagtail.admin.menu import MenuItem, SubmenuMenuItem
from wagtail.admin.ui.components import Component

# 14.1, top to bottom. Anything not named here goes after, in Wagtail's order.
MAIN_ORDER = (
    "首页",
    "文章",
    "文章分类",
    "评论",
    "赛事",
    "报名审核",
    "内战",
    "战队",
    "成员分组",
    "内容审核",
    "头像审核",
    "图片",
    "活动数据",
    "网站页面",
    "用户",
    "设置",
    "后台手册",
)
# Wagtail's own, out of the menu (14.1): 文档, 报告, 帮助.
MAIN_HIDDEN = frozenset({"documents", "reports", "help"})
# The submenu split up onto the first level.
FLATTENED = frozenset({"社区"})
SETTINGS_KEPT = ("全站设置", "字体库", "排版设置", "静态页面", "图片集合", "操作记录")


def _news_index():
    from content.models import ArticleIndexPage

    return ArticleIndexPage.objects.filter(slug="news").first()


def _edits_every_page(user) -> bool:
    from accounts.services import GROUP_CONTENT

    return user.is_superuser or user.groups.filter(name=GROUP_CONTENT).exists()


def arrange_main_menu(request, menu_items) -> None:
    user = request.user
    items = []
    explorer = None
    for item in menu_items:
        name = getattr(item, "name", "")
        if name in MAIN_HIDDEN:
            continue
        if isinstance(item, SubmenuMenuItem) and item.label in FLATTENED:
            items.extend(item.menu.menu_items_for_request(request))
            continue
        if name == "explorer":
            explorer = item
            continue
        items.append(item)

    items.insert(
        0, MenuItem("首页", reverse("wagtailadmin_home"), name="home", icon_name="home")
    )
    # 「文章」: the news section's list, for those who may open the page tree.
    news = _news_index() if explorer is not None else None
    if news is not None:
        items.append(
            MenuItem(
                "文章",
                reverse("wagtailadmin_explore", args=[news.pk]),
                name="articles",
                icon_name="doc-full",
            )
        )
    # The whole tree (首页 pins, 关于我们, the agreements) for the editors.
    if explorer is not None and _edits_every_page(user):
        explorer.label = "网站页面"
        items.append(explorer)

    _in_order(items, MAIN_ORDER)
    menu_items[:] = items


def _in_order(items, labels) -> None:
    """Sort by the design's list and renumber: the sidebar sorts by ``order``
    again when it draws, so the numbers have to agree."""
    rank = {label: index for index, label in enumerate(labels)}
    items.sort(key=lambda item: (rank.get(item.label, len(rank)), item.order))
    for number, item in enumerate(items, start=1):
        item.order = number * 10


def arrange_settings_menu(request, menu_items) -> None:
    for item in menu_items:
        if getattr(item, "name", "") == "collections":
            item.label = "图片集合"
    items = [item for item in menu_items if item.label in SETTINGS_KEPT]
    if request.user.is_superuser:
        items.append(
            MenuItem(
                "操作记录",
                reverse("wagtailadmin_reports:site_history"),
                name="site-history",
                icon_name="history",
            )
        )
    _in_order(items, SETTINGS_KEPT)
    menu_items[:] = items


# --- the greeting ---------------------------------------------------------------


@dataclass(frozen=True)
class Action:
    label: str
    url: str
    primary: bool = False


def roles(user) -> list[str]:
    from accounts.services import STAFF_GROUPS

    if user.is_superuser:
        return ["超级管理员"]
    names = set(user.groups.values_list("name", flat=True))
    return [name for name in STAFF_GROUPS if name in names]


def actions(user) -> list[Action]:
    """The buttons by the greeting: what this person does most (14.1)."""
    from content.services import article_create_admin_url
    from scrims.services import can_manage as runs_scrims
    from tournaments.services import can_manage as runs_tournaments

    found = []
    news = _news_index()
    if news is not None and news.permissions_for_user(user).can_add_subpage():
        url = article_create_admin_url()
        if url:
            found.append(Action("写文章", url, primary=True))
    if runs_tournaments(user):
        found.append(Action("新建赛事", reverse("tournaments:add"), primary=not found))
    if runs_scrims(user):
        found.append(Action("新建内战", reverse("scrims:add"), primary=not found))
    found.append(Action("打开网站", "/"))
    return found


class WelcomePanel(Component):
    name = "site_welcome"
    template_name = "core/admin/welcome_panel.html"
    order = 0

    def get_context_data(self, parent_context):
        user = parent_context["request"].user
        return {
            "nickname": getattr(user, "nickname", "") or user.get_username(),
            "roles": roles(user),
            "actions": actions(user),
        }


# The dashboard keeps only the site's panels (14.1): Wagtail's site summary,
# recent edits, locked pages and moderation lists are left out.
OWN_PANELS = frozenset({"site_welcome", "site_todo", "site_setup"})
