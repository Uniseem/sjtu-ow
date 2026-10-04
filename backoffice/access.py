"""Who gets into the back office and who sees which page (docs/admin.md 2, 4).

``can_enter`` is the door: Wagtail's ``access_admin`` permission, which every
verified member has through 投稿者, each staff role and superusers. The rest
say who may use one tab; the views ask the same functions again, so a typed
address is refused as well as the link being left out.
"""

from __future__ import annotations

ADMIN_PERMISSION = "wagtailadmin.access_admin"


def _signed_in(user) -> bool:
    return bool(user is not None and getattr(user, "is_authenticated", False))


def can_enter(user) -> bool:
    if not _signed_in(user) or not user.is_active:
        return False
    return bool(user.is_superuser or user.has_perm(ADMIN_PERMISSION))


def is_superuser(user) -> bool:
    return bool(_signed_in(user) and user.is_superuser)


def writes_articles(user) -> bool:
    """The article list: everyone inside; plain members see their own."""
    return can_enter(user)


def edits_categories(user) -> bool:
    return can_enter(user) and user.has_perm("content.change_articlecategory")


def edits_site_pages(user) -> bool:
    from content.permissions import user_can_edit_author

    return can_enter(user) and user_can_edit_author(user)


def image_policy():
    """Wagtail's collection-based permissions for pictures."""
    from wagtail.images import get_image_model
    from wagtail.permissions import policy_registry

    return policy_registry.get_by_type(get_image_model())


def uses_images(user) -> bool:
    return can_enter(user) and image_policy().user_has_any_permission(
        user, ["add", "change", "choose"]
    )


def runs_tournaments(user) -> bool:
    from tournaments.services import can_manage

    return can_enter(user) and can_manage(user)


def runs_scrims(user) -> bool:
    from scrims.services import can_manage

    return can_enter(user) and can_manage(user)


def edits_member_groups(user) -> bool:
    return can_enter(user) and user.has_perm("members.change_membergroup")


def reviews_content(user) -> bool:
    from moderation.admin_views import can_review

    return can_enter(user) and can_review(user)


def moderates_comments(user) -> bool:
    from comments.services import can_moderate

    return can_enter(user) and can_moderate(user)


def views_activity(user) -> bool:
    from core.activity import can_view

    return can_enter(user) and can_view(user)


def reads_manual(user) -> bool:
    from core.admin_manual import parts_for

    return can_enter(user) and bool(parts_for(user))
