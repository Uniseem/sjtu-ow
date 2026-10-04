"""Helpers for submitter-only admin customization (design 14.3)."""

from __future__ import annotations

from wagtail.models import PagePermissionTester

from accounts.services import (
    GROUP_AUTHOR,
    GROUP_CONTENT,
    GROUP_SCRIM,
    GROUP_SUBMITTER,
    GROUP_TOURNAMENT,
)

STAFF_BESIDES_SUBMITTER = frozenset(
    {
        GROUP_CONTENT,
        GROUP_AUTHOR,
        GROUP_TOURNAMENT,
        GROUP_SCRIM,
    }
)


def _group_names(user) -> set[str]:
    if user is None or not getattr(user, "is_authenticated", False):
        return set()
    if user.pk is None:
        return set()
    return set(user.groups.values_list("name", flat=True))


def is_submitter_only(user) -> bool:
    """True when the user is a public submitter, not another staff role."""
    if user is None or not getattr(user, "is_authenticated", False):
        return False
    if getattr(user, "is_superuser", False):
        return False
    names = _group_names(user)
    if GROUP_SUBMITTER not in names:
        return False
    return names.isdisjoint(STAFF_BESIDES_SUBMITTER)


def sees_only_own_drafts(user) -> bool:
    """In the page tree, everyone but superusers and content editors sees
    only live pages and their own (14.3). Round 117 widened this from pure
    submitters: tournament and scrim managers are submitters too once their
    email is verified, and verified authors may only edit their own pages,
    yet both were shown other people's unpublished titles."""
    if user is None or not getattr(user, "is_authenticated", False):
        return False
    if getattr(user, "is_superuser", False):
        return False
    return GROUP_CONTENT not in _group_names(user)


def plain_writer(user) -> bool:
    """Members who write without an editor's say: everyone but superusers,
    content editors and verified authors. They get the 「投稿须知」 in the
    editor (round 124) and no 「推荐」 tab (v6.25). Until v6.73 their articles
    went through the 内容审核 workflow; now they publish them themselves."""
    if user is None or not getattr(user, "is_authenticated", False):
        return False
    if getattr(user, "is_superuser", False):
        return False
    return _group_names(user).isdisjoint({GROUP_CONTENT, GROUP_AUTHOR})


def user_can_edit_author(user) -> bool:
    if user is None or not getattr(user, "is_authenticated", False):
        return False
    if getattr(user, "is_superuser", False):
        return True
    return GROUP_CONTENT in _group_names(user)


class OwnArticlesPermissionTester(PagePermissionTester):
    """Members publish their own articles (design 5.4.1, v6.73), and Wagtail
    gives 发布 for the whole section: its publish and unpublish checks do not
    ask whose page it is, so anyone with it could take down anyone's article
    (verified authors could, before v6.73). Here only those who may edit
    every article (content editors, superusers) act on other people's."""

    def _theirs(self) -> bool:
        return (
            self.user.is_superuser
            or "change" in self.permissions
            or self.page.owner_id == self.user.pk
        )

    def can_publish(self):
        return super().can_publish() and self._theirs()

    def can_unpublish(self):
        return super().can_unpublish() and self._theirs()
