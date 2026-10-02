"""Who is on the member showcase, and how it is grouped (design 6.1–6.3)."""

from __future__ import annotations

import re
from dataclasses import dataclass, field

MEMBERS_PATH = "/members/"
# One 职务 field can hold several posts: 「社长、主播」 (design-details 4.3).
TITLE_SEPARATORS = re.compile(r"[、/／,，;；]+")


def split_titles(value) -> list[str]:
    return [
        part.strip() for part in TITLE_SEPARATORS.split(value or "") if part.strip()
    ]


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
    # Every post across the groups, in group order (design-details 4.3).
    titles: list = field(default_factory=list)
    profile: object = None

    @property
    def tags(self) -> list[str]:
        """The posts, or the group names for someone without one."""
        return self.titles or self.groups


@dataclass
class Section:
    group: object
    entries: list  # (titles in this group, Member)


def showcase() -> dict:
    """Visible groups in order, then everyone who has joined, oldest first."""
    from accounts.roles import public_profile
    from members.models import MemberGroup
    from teams.models import TeamMembership

    users = list(
        joined_users().order_by("date_joined", "pk").prefetch_related("game_accounts")
    )
    members = {user.pk: Member(user, profile=public_profile(user)) for user in users}
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
            titles = split_titles(membership.title)
            entries.append((titles, member))
            member.groups.append(group.name)
            member.titles.extend(t for t in titles if t not in member.titles)
        sections.append(Section(group, entries))
    return {"sections": sections, "members": [members[user.pk] for user in users]}


def member_url(user) -> str:
    """A member's own page (design 6.4, v5.5)."""
    return f"{MEMBERS_PATH}{user.pk}/"


ARTICLES_ON_PAGE = 10


@dataclass
class MemberPage:
    """What a member's page shows (design 6.4): only what 1.8 calls public."""

    user: object
    profile: object  # accounts.roles.PublicProfile
    groups: list  # (group, titles in it)
    teams: list  # current teams, each with members_total
    alumni: list  # TeamAlumnus rows: teams this person has left
    articles: list
    article_count: int


def member_page(user) -> MemberPage:
    from django.db.models import Count

    from accounts.roles import public_profile
    from content.models import ArticlePage
    from members.models import MemberGroupMembership
    from teams.models import Team, TeamAlumnus

    groups = [
        (membership.group, split_titles(membership.title))
        for membership in MemberGroupMembership.objects.filter(
            user=user, group__is_visible=True
        )
        .select_related("group")
        .order_by("group__sort_order", "group__name")
    ]
    teams = list(
        Team.objects.filter(
            disbanded_at__isnull=True,
            pk__in=user.team_memberships.values("team_id"),
        )
        .annotate(members_total=Count("memberships"))
        .order_by("name")
    )
    alumni = list(
        TeamAlumnus.objects.filter(user=user, team__disbanded_at__isnull=True)
        .select_related("team")
        .order_by("-left_at")
    )
    published = (
        ArticlePage.objects.live()
        .public()
        .filter(author=user)
        .order_by("-first_published_at")
    )
    return MemberPage(
        user=user,
        profile=public_profile(user),
        groups=groups,
        teams=teams,
        alumni=alumni,
        articles=list(published[:ARTICLES_ON_PAGE]),
        article_count=published.count(),
    )


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
