"""The back office's first page (design 14.1; docs/admin.md 4.1): who you
are and the buttons for what you do most. Used by backoffice.views.home."""

from __future__ import annotations

from dataclasses import dataclass

from django.urls import reverse


def _news_index():
    from content.models import ArticleIndexPage

    return ArticleIndexPage.objects.filter(slug="news").first()


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
