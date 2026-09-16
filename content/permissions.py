"""Helpers for submitter-only admin customization (design 14.3)."""

from __future__ import annotations

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


def user_can_edit_author(user) -> bool:
    if user is None or not getattr(user, "is_authenticated", False):
        return False
    if getattr(user, "is_superuser", False):
        return True
    return GROUP_CONTENT in _group_names(user)
