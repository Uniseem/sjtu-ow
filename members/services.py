"""Who is on the member showcase, and how it is grouped (design 6.1–6.3)."""

from __future__ import annotations

from dataclasses import dataclass, field

MEMBERS_PATH = "/members/"


def joined_users():
    """Active accounts with at least one verified email (design 6.1)."""
    from accounts.models import User

    return User.objects.filter(is_active=True, emailaddress__verified=True).distinct()


def is_joined(user) -> bool:
    return joined_users().filter(pk=user.pk).exists()


@dataclass
class Member:
    user: object
    teams: list = field(default_factory=list)
    groups: list = field(default_factory=list)


@dataclass
class Section:
    group: object
    entries: list  # (title, Member)


def showcase() -> dict:
    """Visible groups in order, then everyone who has joined, oldest first."""
    from members.models import MemberGroup
    from teams.models import TeamMembership

    users = list(joined_users().order_by("date_joined", "pk"))
    members = {user.pk: Member(user) for user in users}
    for membership in (
        TeamMembership.objects.filter(
            user_id__in=members, team__disbanded_at__isnull=True
        )
        .select_related("team")
        .order_by("team__name")
    ):
        members[membership.user_id].teams.append(membership.team)

    sections = []
    for group in MemberGroup.objects.filter(is_visible=True).order_by(
        "sort_order", "name"
    ):
        entries = []
        for membership in group.memberships.select_related("user").order_by(
            "sort_order", "user__nickname"
        ):
            member = members.get(membership.user_id)
            if member is None:
                continue  # left, deactivated or not verified
            entries.append((membership.title, member))
            member.groups.append(group.name)
        sections.append(Section(group, entries))
    return {"sections": sections, "members": [members[user.pk] for user in users]}


def refresh_page() -> None:
    from core import prerender

    prerender.request_page(MEMBERS_PATH, kind="members")


MEMBER_PERMISSIONS = (
    "add_membergroup",
    "change_membergroup",
    "delete_membergroup",
    "view_membergroup",
)


def assign_member_permissions() -> list[str]:
    """Content editors manage member groups (design 4.1, 6.2)."""
    from django.contrib.auth.models import Group, Permission

    from accounts.services import GROUP_CONTENT

    permissions = list(
        Permission.objects.filter(
            content_type__app_label="members", codename__in=MEMBER_PERMISSIONS
        )
    )
    granted = []
    group = Group.objects.filter(name=GROUP_CONTENT).first()
    if group is not None and permissions:
        group.permissions.add(*permissions)
        granted.append(group.name)
    return granted
