"""The admin's eight sections and the tabs inside them (design 14.1, v6.71,
round 193).

The sidebar keeps only 首页, 内容, 活动, 成员, 审核, 数据, 设置 and 手册, each a
plain link; the pages of a section are tabs along its top. Sections are
built from the menu items this person would have seen anyway, so who sees
what is still each page's own permission check. Every tab is the page it
always was, at the same address.

Wagtail lights the sidebar item with the longest address prefix of the page,
which after merging would light 「首页」 (``/admin/``) on most pages; the tab
strip says which section the page belongs to and admin.css lights that one.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

from django.conf import settings
from wagtail.admin.menu import MenuItem, SubmenuMenuItem

# (key, sidebar label, icon, tab keys left to right)
SECTIONS = (
    ("home", "首页", "home", ("home",)),
    ("content", "内容", "doc-full", ("articles", "categories", "pages", "images")),
    ("events", "活动", "date", ("tournaments", "scrims")),
    ("members", "成员", "group", ("people", "teams", "member_groups")),
    (
        "review",
        "审核",
        "tasks",
        ("registrations", "moderation", "avatars", "comments"),
    ),
    ("data", "数据", "table", ("activity",)),
    (
        "settings",
        "设置",
        "cogs",
        ("site_settings", "fonts", "typography", "prerender", "collections", "history"),
    ),
    ("manual", "手册", "help", ("manual",)),
)
TAB_LABELS = {
    "home": "首页",
    "articles": "文章",
    "categories": "分类",
    "pages": "网站页面",
    "images": "图片",
    "tournaments": "赛事",
    "scrims": "内战",
    "people": "用户与权限",
    "teams": "战队",
    "member_groups": "成员分组",
    "registrations": "报名",
    "moderation": "内容",
    "avatars": "头像",
    "comments": "评论",
    "activity": "活动数据",
    "site_settings": "全站设置",
    "fonts": "字体库",
    "typography": "排版设置",
    "prerender": "静态页面",
    "collections": "图片集合",
    "history": "操作记录",
    "manual": "手册",
    # Under 用户与权限.
    "users": "用户",
    "groups": "用户组",
    "feature_groups": "用户组功能限制",
    "feature_users": "用户功能规则",
}
PEOPLE = ("users", "groups", "feature_groups", "feature_users")
# Where each tab's pages live, under the admin prefix. The longest match wins;
# the page tree is decided by the page (``_page_tab``).
PREFIXES = (
    ("comments/", "comments"),
    ("tournaments/", "tournaments"),
    ("announce/tournament/", "tournaments"),
    ("registrations/", "registrations"),
    ("scrims/", "scrims"),
    ("announce/scrim/", "scrims"),
    ("teams/", "teams"),
    ("snippets/members/membergroup/", "member_groups"),
    ("snippets/content/articlecategory/", "categories"),
    ("moderation/", "moderation"),
    ("avatars/", "avatars"),
    ("images/", "images"),
    ("activity/", "activity"),
    ("users/", "users"),
    ("groups/", "groups"),
    ("feature_group_restrictions/", "feature_groups"),
    ("feature_user_rules/", "feature_users"),
    ("settings/fonts/", "fonts"),
    ("settings/typography/", "typography"),
    ("settings/prerender/", "prerender"),
    ("settings/", "site_settings"),
    ("collections/", "collections"),
    ("reports/site-history/", "history"),
    ("manual/", "manual"),
    ("pages/", "pages"),
)
PAGE_ID = re.compile(r"pages/(?:add/[^/]+/[^/]+/)?(\d{1,18})/")


@dataclass
class Tab:
    key: str
    label: str
    url: str
    count: int = 0
    children: list[Tab] = field(default_factory=list)


@dataclass
class Section:
    key: str
    label: str
    icon: str
    tabs: list[Tab]

    @property
    def url(self) -> str:
        return self.tabs[0].url


def _admin(path: str) -> str:
    return getattr(settings, "ADMIN_URL_PREFIX", "/admin/") + path


def key_for_path(path: str) -> str:
    """The tab a page belongs to by its address alone ("" if none)."""
    if path == _admin(""):
        return "home"
    best, found = 0, ""
    for prefix, key in PREFIXES:
        full = _admin(prefix)
        if path.startswith(full) and len(full) > best:
            best, found = len(full), key
    return found


def _page_tab(path: str) -> str:
    """In the page tree: 「文章」 for the news section and what is under it,
    「网站页面」 for the rest."""
    from wagtail.models import Page

    from core.admin_home import _news_index

    match = PAGE_ID.search(path)
    news = _news_index()
    if not match or news is None:
        return "pages"
    page = Page.objects.filter(pk=int(match.group(1))).only("path").first()
    if page is not None and page.path.startswith(news.path):
        return "articles"
    return "pages"


def _flatten(request, items):
    for item in items:
        if isinstance(item, SubmenuMenuItem):
            yield from _flatten(request, item.menu.menu_items_for_request(request))
        else:
            yield item


def _item_key(item) -> str:
    name = getattr(item, "name", "")
    if name in ("home", "articles"):
        return name
    if name == "explorer":
        return "pages"
    return key_for_path(getattr(item, "url", "") or "")


def build(request, menu_items) -> tuple[list[Section], list]:
    """This person's sections, and any menu item that belongs to none (kept
    in the sidebar as it was, so nothing new goes missing)."""
    tabs: dict[str, Tab] = {}
    leftovers = []
    for item in _flatten(request, menu_items):
        key = _item_key(item)
        if not key:
            leftovers.append(item)
        elif key not in tabs:
            tabs[key] = Tab(key, TAB_LABELS[key], item.url)
    people = [tabs.pop(key) for key in PEOPLE if key in tabs]
    if people:
        tabs["people"] = Tab(
            "people", TAB_LABELS["people"], people[0].url, children=people
        )
    sections = []
    for key, label, icon, keys in SECTIONS:
        found = [tabs[tab] for tab in keys if tab in tabs]
        if found:
            sections.append(Section(key, label, icon, found))
    return sections, leftovers


class SectionMenuItem(MenuItem):
    def __init__(self, section: Section, order: int):
        super().__init__(
            section.label,
            section.url,
            name=f"section-{section.key}",
            icon_name=section.icon,
            attrs={"data-section": section.key},
            order=order,
        )


def arrange(request, menu_items) -> None:
    sections, leftovers = build(request, menu_items)
    request.admin_sections = sections
    items = [
        SectionMenuItem(section, (number + 1) * 10)
        for number, section in enumerate(sections)
    ]
    for number, item in enumerate(leftovers, start=len(items) + 1):
        item.order = number * 10
        items.append(item)
    menu_items[:] = items


@dataclass
class Place:
    section: Section | None
    tab: Tab | None
    child: Tab | None


def locate(request, sections: list[Section]) -> Place:
    path = request.path
    key = key_for_path(path)
    if key == "pages":
        key = _page_tab(path)
    for section in sections:
        for tab in section.tabs:
            if tab.key == key:
                return Place(section, tab, None)
            for child in tab.children:
                if child.key == key:
                    return Place(section, tab, child)
    return Place(None, None, None)


def count_review_tabs(user, section: Section) -> None:
    """The waiting work on the 审核 tabs (the same counts as the dashboard)."""
    from core import admin_todo

    counters = {
        "registrations": admin_todo.pending_registrations,
    }
    for tab in section.tabs:
        if tab.key in counters:
            tab.count = counters[tab.key]()


def sections_for(request) -> list[Section]:
    """Built by the menu hook while the sidebar is drawn; built here when a
    page draws its tabs without the sidebar."""
    found = getattr(request, "admin_sections", None)
    if found is None:
        from wagtail.admin.menu import admin_menu

        admin_menu.menu_items_for_request(request)
        found = getattr(request, "admin_sections", [])
    return found


def tab_strip(request) -> str:
    from django.template.loader import render_to_string

    user = getattr(request, "user", None)
    if not getattr(user, "is_authenticated", False):
        return ""
    sections = sections_for(request)
    place = locate(request, sections)
    if place.section is not None and place.section.key == "review":
        count_review_tabs(user, place.section)
    return render_to_string(
        "core/admin/section_tabs.html", {"place": place}, request=request
    )
