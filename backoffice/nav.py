"""The eight sections, their tabs and where a page sits (docs/admin.md 4).

Each view says where it belongs with ``placed(section, tab)``; nothing is
guessed from the address. ``placed`` is also the door: a visitor who is not
signed in goes to the sign-in page, someone without ``access_admin`` gets a
403, and so does someone the tab is not for (v7.3: the tab's ``allowed``, the
same function that decides whether its link is drawn). A page stricter than
its tab says so with ``allowed=``; the view itself checks only what is finer
than a page (this article, that collection).
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field
from functools import cached_property, wraps

from django.contrib.auth.views import redirect_to_login
from django.core.exceptions import PermissionDenied
from django.urls import reverse
from django.views.decorators.cache import never_cache

from backoffice import access


@dataclass(frozen=True)
class Tab:
    key: str
    label: str
    url_name: str
    allowed: Callable
    count: Callable | None = None


@dataclass(frozen=True)
class Section:
    key: str
    label: str
    tabs: tuple[Tab, ...]
    # Sections with one page (首页, 手册) are a single tab without a strip.
    strip: bool = True


def _pending_registrations(user) -> int:
    from core.admin_todo import pending_registrations

    return pending_registrations()


SECTIONS: tuple[Section, ...] = (
    Section(
        "home",
        "首页",
        (Tab("home", "首页", "backoffice:home", access.can_enter),),
        strip=False,
    ),
    Section(
        "content",
        "内容",
        (
            Tab("articles", "文章", "backoffice:articles", access.writes_articles),
            Tab("categories", "分类", "backoffice:categories", access.edits_categories),
            Tab("pages", "网站页面", "backoffice:pages", access.edits_site_pages),
            Tab("images", "图片", "backoffice:images", access.uses_images),
        ),
    ),
    Section(
        "events",
        "活动",
        (
            Tab("tournaments", "赛事", "tournaments:index", access.runs_tournaments),
            Tab("scrims", "内战", "scrims:index", access.runs_scrims),
        ),
    ),
    Section(
        "members",
        "成员",
        (
            Tab("users", "用户与权限", "backoffice:users", access.is_superuser),
            Tab("teams", "战队", "teams:index", access.is_superuser),
            Tab(
                "groups",
                "成员分组",
                "backoffice:member_groups",
                access.edits_member_groups,
            ),
        ),
    ),
    Section(
        "review",
        "审核",
        (
            Tab(
                "registrations",
                "报名",
                "registration_review_index",
                access.runs_tournaments,
                count=_pending_registrations,
            ),
            Tab("moderation", "内容", "moderation_index", access.reviews_content),
            Tab("avatars", "头像", "avatar_review", access.reviews_content),
            Tab("comments", "评论", "comments:index", access.moderates_comments),
        ),
    ),
    Section(
        "data",
        "数据",
        (Tab("activity", "活动数据", "admin_activity", access.views_activity),),
    ),
    Section(
        "settings",
        "设置",
        (
            Tab("site", "全站设置", "backoffice:site_settings", access.is_superuser),
            Tab("fonts", "字体库", "core_font_index", access.is_superuser),
            Tab("typography", "排版设置", "core_typography", access.is_superuser),
            Tab("prerender", "静态页面", "core_prerender_index", access.is_superuser),
            Tab("log", "操作记录", "backoffice:log", access.is_superuser),
        ),
    ),
    Section(
        "manual",
        "手册",
        (Tab("manual", "后台手册", "admin_manual", access.reads_manual),),
        strip=False,
    ),
)

# 「用户与权限」 has a second row (docs/admin.md 4.4).
SUBTABS: dict[tuple[str, str], tuple[tuple[str, str, str], ...]] = {
    ("members", "users"): (
        ("users", "用户", "backoffice:users"),
        ("roles", "角色", "backoffice:roles"),
    ),
}

BY_KEY = {section.key: section for section in SECTIONS}


@dataclass(frozen=True)
class Place:
    section: str
    tab: str | None = None
    subtab: str | None = None


@dataclass
class Link:
    key: str
    label: str
    url: str
    current: bool = False
    count: int = 0


@dataclass
class Navigation:
    """What the top bar and the page head draw for this person on this page."""

    user: object
    place: Place
    _allowed: dict = field(default_factory=dict)

    def _tab_allowed(self, tab: Tab) -> bool:
        if tab.key not in self._allowed:
            self._allowed[tab.key] = bool(tab.allowed(self.user))
        return self._allowed[tab.key]

    @cached_property
    def sections(self) -> list[Link]:
        links = []
        for section in SECTIONS:
            first = next((t for t in section.tabs if self._tab_allowed(t)), None)
            if first is None:
                continue
            links.append(
                Link(
                    section.key,
                    section.label,
                    reverse(first.url_name),
                    current=section.key == self.place.section,
                )
            )
        return links

    @cached_property
    def section(self) -> Section | None:
        return BY_KEY.get(self.place.section)

    @cached_property
    def tabs(self) -> list[Link]:
        section = self.section
        if section is None or not section.strip:
            return []
        links = [
            Link(
                tab.key,
                tab.label,
                reverse(tab.url_name),
                current=tab.key == self.place.tab,
                count=tab.count(self.user) if tab.count else 0,
            )
            for tab in section.tabs
            if self._tab_allowed(tab)
        ]
        # One page is not a choice: no strip (docs/admin.md 3).
        return links if len(links) > 1 else []

    @cached_property
    def subtabs(self) -> list[Link]:
        rows = SUBTABS.get((self.place.section, self.place.tab or ""), ())
        return [
            Link(key, label, reverse(url_name), current=key == self.place.subtab)
            for key, label, url_name in rows
        ]


def tab_for(section: str, tab: str) -> Tab:
    for item in BY_KEY[section].tabs:
        if item.key == tab:
            return item
    raise ValueError(f"「{BY_KEY[section].label}」里没有这个标签：{tab}")


def placed(
    section: str,
    tab: str | None = None,
    subtab: str | None = None,
    *,
    allowed: Callable | None = None,
):
    """Put a view in the back office: the door, this page's permission (the
    tab's unless ``allowed`` says stricter), then where it sits."""

    if section not in BY_KEY:
        raise ValueError(f"没有这个大类：{section}")
    gate = allowed or (tab_for(section, tab).allowed if tab else access.can_enter)

    def decorate(view):
        @wraps(view)
        @never_cache
        def wrapper(request, *args, **kwargs):
            if not request.user.is_authenticated:
                return redirect_to_login(request.get_full_path())
            if not access.can_enter(request.user):
                raise PermissionDenied("没有进入后台的权限。")
            if not gate(request.user):
                raise PermissionDenied("没有打开这一页的权限。")
            request.backoffice_place = Place(section, tab, subtab)
            return view(request, *args, **kwargs)

        wrapper.backoffice_place = Place(section, tab, subtab)
        wrapper.backoffice_gate = gate
        return wrapper

    return decorate
