"""Account helpers: groups, profile completeness, game IDs."""

from __future__ import annotations

from django.contrib.auth.models import Group, Permission
from django.core.exceptions import ValidationError

from accounts.models import ContactMethod, GameAccount, User

GROUP_SJTU = "交大用户"
GROUP_EXTERNAL = "校外用户"
GROUP_CONTENT = "内容编辑"
GROUP_TOURNAMENT = "赛事管理员"
GROUP_SCRIM = "内战管理员"
GROUP_AUTHOR = "认证作者"
GROUP_SUBMITTER = "投稿者"

STAFF_GROUPS = (
    GROUP_CONTENT,
    GROUP_TOURNAMENT,
    GROUP_SCRIM,
    GROUP_AUTHOR,
    GROUP_SUBMITTER,
)
ALL_PRESET_GROUPS = (GROUP_SJTU, GROUP_EXTERNAL, *STAFF_GROUPS)
CONTACT_VIEW_GROUPS = (GROUP_TOURNAMENT, GROUP_SCRIM)


def ensure_user_groups() -> tuple[Group, Group]:
    """Create the two automatic groups if they are missing."""
    sjtu, _ = Group.objects.get_or_create(name=GROUP_SJTU)
    external, _ = Group.objects.get_or_create(name=GROUP_EXTERNAL)
    return sjtu, external


def ensure_preset_groups() -> dict[str, Group]:
    """Create every preset group. Does not change membership."""
    groups = {}
    for name in ALL_PRESET_GROUPS:
        groups[name], _ = Group.objects.get_or_create(name=name)
    return groups


def sync_sjtu_groups(user) -> None:
    """Assign 交大用户 or 校外用户 from is_sjtu; leave other groups alone."""
    if user.pk is None:
        return
    sjtu, external = ensure_user_groups()
    if user.is_sjtu:
        user.groups.add(sjtu)
        user.groups.remove(external)
    else:
        user.groups.add(external)
        user.groups.remove(sjtu)


def max_game_accounts() -> int:
    from core.models import SiteSettings

    site = SiteSettings.load()
    return int(site.max_game_accounts or 5)


def profile_gaps(user: User) -> list[tuple[str, str, str]]:
    """Return missing profile items as (label, url_name, hint)."""
    gaps = []
    if not user.game_accounts.exists():
        gaps.append(("游戏 ID", "me_game_accounts", "至少绑定 1 个游戏 ID"))
    if not user.contact_methods.exists():
        gaps.append(("联系方式", "me_contacts", "至少填写 1 种联系方式"))
    return gaps


def profile_is_complete(user: User) -> bool:
    return not profile_gaps(user)


def deletion_blocked_reason(account: GameAccount) -> str | None:
    """Return a user-facing reason, or None if the game ID may be deleted.

    M6: refuse when this ID is used in an unfinished scrim signup
    (prompt to cancel the scrim signup first).
    M3: deleting the ID also deletes LFG posts that use it.
    Tournament registration snapshots (M4) are not affected.
    """
    _ = account
    return None


def add_game_account(user: User, **fields) -> GameAccount:
    if user.game_accounts.count() >= max_game_accounts():
        raise ValidationError(f"每人最多绑定 {max_game_accounts()} 个游戏 ID。")
    account = GameAccount(user=user, **fields)
    account.full_clean()
    account.save()
    return account


def add_contact_method(user: User, **fields) -> ContactMethod:
    contact = ContactMethod(user=user, **fields)
    contact.full_clean()
    contact.save()
    return contact


def assign_round_permissions() -> None:
    """Attach permissions this milestone can actually grant. Idempotent."""
    groups = ensure_preset_groups()
    access_admin = Permission.objects.get(
        content_type__app_label="wagtailadmin",
        codename="access_admin",
    )
    view_contact = Permission.objects.get(
        content_type__app_label="accounts",
        codename="view_contactmethod",
    )
    for name in STAFF_GROUPS:
        groups[name].permissions.add(access_admin)
    for name in CONTACT_VIEW_GROUPS:
        groups[name].permissions.add(view_contact)
