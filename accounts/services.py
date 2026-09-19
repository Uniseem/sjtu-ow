"""Account helpers: groups, profile completeness, game IDs."""

from __future__ import annotations

from django.contrib.auth.models import Group, Permission
from django.core.exceptions import ValidationError

from accounts.models import (
    ContactMethod,
    Feature,
    FeatureUserRule,
    GameAccount,
    User,
)
from accounts.permissions import can_use
from accounts.ranks import format_rank

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

    Design 9.2: a signup points at the game ID it was made with, so the ID
    cannot go while an unfinished scrim still uses it — cancel the signup
    first. Tournament roster snapshots (M4) hold copies, not references.
    """
    from scrims.models import ScrimStatus

    signup = (
        account.scrim_signups.filter(
            scrim__status__in=[ScrimStatus.DRAFT, ScrimStatus.PUBLISHED]
        )
        .select_related("scrim")
        .first()
    )
    if signup is not None:
        return (
            f"这个游戏 ID 正用于内战「{signup.scrim.title}」的报名，"
            f"请先取消报名再删除。"
        )
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


def email_is_verified(user) -> bool:
    if user is None or not getattr(user, "pk", None):
        return False
    from allauth.account.models import EmailAddress

    return EmailAddress.objects.filter(user=user, verified=True).exists()


def user_should_be_submitter(user) -> bool:
    if user is None or not getattr(user, "pk", None):
        return False
    if not user.is_active:
        return False
    if not email_is_verified(user):
        return False
    return can_use(user, Feature.ARTICLE_SUBMIT)


def sync_submitter_group(user) -> bool:
    """Add or remove 「投稿者」 to match 5.4.2. Returns whether the user is in it."""
    if user is None or not getattr(user, "pk", None):
        return False
    group, _ = Group.objects.get_or_create(name=GROUP_SUBMITTER)
    should = user_should_be_submitter(user)
    in_group = user.groups.filter(pk=group.pk).exists()
    if should and not in_group:
        user.groups.add(group)
        return True
    if not should and in_group:
        user.groups.remove(group)
        return False
    return should


def sync_submitters_for_users(users) -> None:
    for user in users:
        sync_submitter_group(user)


def sync_submitters_for_group(group: Group) -> None:
    sync_submitters_for_users(group.user_set.all())


def sync_all_submitter_memberships() -> int:
    """Recompute 投稿者 for verified users and anyone already in the group."""
    from allauth.account.models import EmailAddress

    group, _ = Group.objects.get_or_create(name=GROUP_SUBMITTER)
    ids = set(group.user_set.values_list("pk", flat=True))
    ids.update(
        EmailAddress.objects.filter(verified=True).values_list("user_id", flat=True)
    )
    changed = 0
    for user in User.objects.filter(pk__in=ids):
        before = user.groups.filter(pk=group.pk).exists()
        after = sync_submitter_group(user)
        if before != after:
            changed += 1
    return changed


def refresh_nickname_pages(user) -> None:
    """Regenerate the public pages that print this user's nickname (13.13.4)."""
    from content.models import ArticlePage
    from core import prerender

    for membership in user.team_memberships.select_related("team"):
        if not membership.team.is_disbanded:
            prerender.request_page(membership.team.get_absolute_url(), kind="team")
    for signup in user.scrim_signups.select_related("scrim"):
        if signup.scrim.is_public:
            prerender.request_page(f"/scrims/{signup.scrim_id}/", kind="scrim")
    for article in ArticlePage.objects.live().public().filter(author=user):
        url = article.get_url()
        if url:
            prerender.request_page(url, kind="article")
    prerender.request_page("/members/", kind="members")


DELETED_NICKNAME = "已注销用户"
DELETED_NOTE = "用户自行注销"


class AccountDeletionError(Exception):
    """Why the account cannot be deleted right now; shown to the user."""


def deletion_blockers(user) -> list[str]:
    """A captain must hand over or disband first (design 3.8, 7.4)."""
    from teams.models import TeamMembership, TeamRole

    captained = TeamMembership.objects.filter(
        user=user, role=TeamRole.CAPTAIN, team__disbanded_at__isnull=True
    ).select_related("team")
    return [
        f"你是战队「{membership.team.name}」的队长，请先转让队长或解散战队。"
        for membership in captained
    ]


def delete_account(user) -> None:
    """Anonymise the account in place (design 3.8). Users are never deleted.

    Registration roster snapshots and their logs stay: they record what was
    submitted. Articles stay and show the new nickname.
    """
    from allauth.account.models import EmailAddress
    from django.db import transaction

    from members.models import MemberGroupMembership
    from moderation.models import ModerationItem, TargetType
    from scrims.services import remove_signups_of
    from teams.services import leave_all_teams

    blockers = deletion_blockers(user)
    if blockers:
        raise AccountDeletionError(blockers[0])
    with transaction.atomic():
        remove_signups_of(user)  # before game IDs: signups PROTECT them
        leave_all_teams(user)
        user.game_accounts.all().delete()
        MemberGroupMembership.objects.filter(user=user).delete()  # design 3.8
        user.contact_methods.all().delete()
        EmailAddress.objects.filter(user=user).delete()
        FeatureUserRule.objects.filter(user=user).delete()
        user.email = f"deleted-{user.pk}@deleted.invalid"
        user.nickname = DELETED_NICKNAME
        user.is_sjtu = False
        user.sjtu_verified_via = None
        user.sjtu_verified_at = None
        user.is_active = False
        user.is_staff = False
        user.deactivation_note = DELETED_NOTE
        user.set_unusable_password()
        user.save()
        # After the save: its signal puts everyone back in 交大用户 / 校外用户.
        user.groups.clear()
        # The review queue keeps a copy of each nickname it checked, including
        # the one the save above just sent.
        ModerationItem.objects.filter(
            target_type=TargetType.NICKNAME, target_id=user.pk
        ).delete()


def personal_data(user) -> dict:
    """Everything the site holds about the user, for download (design 3.8).

    Only the user's own data: no teammates' contacts, no admin records.
    """
    from content.models import ArticlePage
    from members.models import MemberGroupMembership
    from scrims.models import ScrimSignup
    from teams.models import TeamApplication, TeamMembership
    from tournaments.models import RegistrationMember

    def when(value):
        return value.isoformat() if value else None

    return {
        "account": {
            "email": user.email,
            "nickname": user.nickname,
            "is_sjtu": user.is_sjtu,
            "date_joined": when(user.date_joined),
            "agreed_terms_at": when(user.agreed_terms_at),
            "agreed_cross_border_at": when(user.agreed_cross_border_at),
        },
        "game_accounts": [
            {
                "battletag": account.battletag,
                "rank_tank": format_rank(account.rank_tank),
                "rank_damage": format_rank(account.rank_damage),
                "rank_support": format_rank(account.rank_support),
                "ranks_updated_at": when(account.ranks_updated_at),
            }
            for account in user.game_accounts.all()
        ],
        "contact_methods": [
            {"type": contact.get_type_display(), "value": contact.value}
            for contact in user.contact_methods.all()
        ],
        "teams": [
            {
                "team": membership.team.name,
                "role": membership.get_role_display(),
                "joined_at": when(membership.joined_at),
            }
            for membership in TeamMembership.objects.filter(user=user).select_related(
                "team"
            )
        ],
        "team_applications": [
            {
                "team": application.team.name,
                "status": application.get_status_display(),
                "message": application.message,
                "created_at": when(application.created_at),
            }
            for application in TeamApplication.objects.filter(
                applicant=user
            ).select_related("team")
        ],
        "tournament_registrations": [
            {
                "tournament": member.registration.tournament.title,
                "team": member.registration.team_name,
                "status": member.registration.get_status_display(),
                "nickname_snapshot": member.nickname,
                "battletag_snapshot": member.battletag,
            }
            for member in RegistrationMember.objects.filter(user=user).select_related(
                "registration__tournament"
            )
        ],
        "scrim_signups": [
            {
                "scrim": signup.scrim.title,
                "starts_at": when(signup.scrim.starts_at),
                "battletag": signup.game_account.battletag,
                "roles": [
                    label
                    for field, label in (
                        ("role_tank", "坦克"),
                        ("role_damage", "输出"),
                        ("role_support", "支援"),
                    )
                    if getattr(signup, field)
                ],
            }
            for signup in ScrimSignup.objects.filter(user=user).select_related(
                "scrim", "game_account"
            )
        ],
        "member_groups": [
            {"group": membership.group.name, "title": membership.title}
            for membership in MemberGroupMembership.objects.filter(
                user=user
            ).select_related("group")
        ],
        "articles": [
            {"title": page.title, "url": page.get_url()}
            for page in ArticlePage.objects.filter(author=user)
        ],
    }
