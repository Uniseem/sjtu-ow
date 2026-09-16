"""Team business rules (design 7). Every guard lives here, not in the views."""

from __future__ import annotations

import logging

from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction
from django.db.models import Q
from django.db.models.functions import Lower
from django.utils import timezone

from teams.models import (
    ApplicationStatus,
    Team,
    TeamApplication,
    TeamMembership,
    TeamRole,
)

logger = logging.getLogger(__name__)


class TeamError(Exception):
    """Something the user is not allowed to do right now; message is shown."""


def site_settings():
    from core.models import SiteSettings

    return SiteSettings.load()


def max_members() -> int:
    return int(site_settings().team_max_members or 10)


def max_captained() -> int:
    return int(site_settings().team_max_captained or 3)


def active_teams():
    return Team.objects.filter(disbanded_at__isnull=True)


def name_taken(name: str, exclude_pk=None) -> bool:
    query = active_teams().annotate(lowered=Lower("name")).filter(lowered=name.lower())
    if exclude_pk:
        query = query.exclude(pk=exclude_pk)
    return query.exists()


def captained_count(user) -> int:
    return TeamMembership.objects.filter(
        user=user,
        role=TeamRole.CAPTAIN,
        team__disbanded_at__isnull=True,
    ).count()


def is_member(team, user) -> bool:
    if not getattr(user, "is_authenticated", False):
        return False
    return TeamMembership.objects.filter(team=team, user=user).exists()


def is_captain(team, user) -> bool:
    if not getattr(user, "is_authenticated", False):
        return False
    return TeamMembership.objects.filter(
        team=team, user=user, role=TeamRole.CAPTAIN
    ).exists()


def is_full(team) -> bool:
    return team.memberships.count() >= max_members()


def create_team(*, user, name, description="", logo=None, is_recruiting=True) -> Team:
    """Create a team; the creator becomes its captain (design 7.1)."""
    from accounts.permissions import can_use, feature_denied_message

    if not can_use(user, "team_create"):
        raise TeamError(feature_denied_message("team_create"))
    if captained_count(user) >= max_captained():
        raise TeamError(f"每人最多同时担任 {max_captained()} 支战队的队长。")
    if name_taken(name):
        raise TeamError("已经有同名的战队了，换一个队名吧。")

    try:
        with transaction.atomic():
            team = Team.objects.create(
                name=name,
                description=description,
                logo=logo,
                is_recruiting=is_recruiting,
            )
            TeamMembership.objects.create(team=team, user=user, role=TeamRole.CAPTAIN)
    except IntegrityError as exc:
        # Someone took the name between the check and the insert.
        raise TeamError("已经有同名的战队了，换一个队名吧。") from exc
    on_team_changed(team, author=user)
    return team


def update_team(*, team, user, name, description, logo, is_recruiting) -> Team:
    if not is_captain(team, user) and not user.is_superuser:
        raise TeamError("只有队长可以修改战队资料。")
    if team.is_disbanded:
        raise TeamError("战队已解散。")
    if name_taken(name, exclude_pk=team.pk):
        raise TeamError("已经有同名的战队了，换一个队名吧。")
    team.name = name
    team.description = description
    team.logo = logo
    team.is_recruiting = is_recruiting
    try:
        team.save()
    except IntegrityError as exc:
        raise TeamError("已经有同名的战队了，换一个队名吧。") from exc
    on_team_changed(team, author=user)
    return team


def can_apply(team, user) -> tuple[bool, str]:
    """All the conditions from design 7.3, with the reason to show."""
    from accounts.models import GameAccount
    from accounts.permissions import can_use, feature_denied_message

    if not getattr(user, "is_authenticated", False):
        return False, "请先登录。"
    if not can_use(user, "team_apply"):
        return False, feature_denied_message("team_apply")
    if team.is_disbanded:
        return False, "战队已解散。"
    if is_member(team, user):
        return False, "你已经是这支战队的成员了。"
    if not team.is_recruiting:
        return False, "这支战队暂时不招募。"
    if is_full(team):
        return False, "战队人数已满。"
    if not GameAccount.objects.filter(user=user).exists():
        return False, "请先在个人中心添加至少一个游戏 ID。"
    if TeamApplication.objects.filter(
        team=team, applicant=user, status=ApplicationStatus.PENDING
    ).exists():
        return False, "你对这支战队还有一条待审批的申请。"
    return True, ""


def apply_to_team(*, team, user, roles, message="") -> TeamApplication:
    allowed, reason = can_apply(team, user)
    if not allowed:
        raise TeamError(reason)
    if not any(roles.values()):
        raise TeamError("请至少选择一个意向位置。")
    application = TeamApplication.objects.create(
        team=team,
        applicant=user,
        role_tank=bool(roles.get("tank")),
        role_damage=bool(roles.get("damage")),
        role_support=bool(roles.get("support")),
        message=message,
    )
    from teams import notifications

    notifications.application_submitted(application)
    if message:
        _submit_moderation(
            target_type="application_message",
            target_id=application.pk,
            field="message",
            text=message,
            url=f"/teams/{team.pk}/manage/",
            author=user,
        )
    return application


@transaction.atomic
def approve_application(*, application, actor) -> TeamApplication:
    """Approve inside one write transaction, re-checking the limits (7.3)."""
    application = TeamApplication.objects.select_for_update().get(pk=application.pk)
    team = application.team
    if not is_captain(team, actor) and not actor.is_superuser:
        raise TeamError("只有队长可以审批入队申请。")
    if application.status != ApplicationStatus.PENDING:
        raise TeamError("这条申请已经处理过了。")
    if team.is_disbanded:
        raise TeamError("战队已解散。")
    if is_member(team, application.applicant):
        application.status = ApplicationStatus.CANCELLED
        application.decided_by = actor
        application.decided_at = timezone.now()
        application.decision_note = "申请人已经是成员"
        application.save()
        raise TeamError("申请人已经是这支战队的成员了。")
    if is_full(team):
        raise TeamError("战队人数已满，无法通过。")

    TeamMembership.objects.create(
        team=team, user=application.applicant, role=TeamRole.MEMBER
    )
    application.status = ApplicationStatus.APPROVED
    application.decided_by = actor
    application.decided_at = timezone.now()
    application.save()
    transaction.on_commit(lambda: _after_approval(application, team, actor))
    return application


def _after_approval(application, team, actor):
    from teams import notifications

    notifications.application_decided(application)
    on_team_changed(team, author=actor)


def reject_application(*, application, actor, note="") -> TeamApplication:
    if not is_captain(application.team, actor) and not actor.is_superuser:
        raise TeamError("只有队长可以审批入队申请。")
    if application.status != ApplicationStatus.PENDING:
        raise TeamError("这条申请已经处理过了。")
    application.status = ApplicationStatus.REJECTED
    application.decided_by = actor
    application.decided_at = timezone.now()
    application.decision_note = note[:200]
    application.save()
    from teams import notifications

    notifications.application_decided(application)
    return application


def cancel_application(*, application, actor) -> TeamApplication:
    if application.applicant_id != actor.pk:
        raise TeamError("只能撤回自己的申请。")
    if application.status != ApplicationStatus.PENDING:
        raise TeamError("这条申请已经处理过了。")
    application.status = ApplicationStatus.CANCELLED
    application.decided_at = timezone.now()
    application.save()
    return application


def leave_team(*, team, user) -> None:
    membership = TeamMembership.objects.filter(team=team, user=user).first()
    if membership is None:
        raise TeamError("你不是这支战队的成员。")
    if membership.is_captain:
        raise TeamError("队长不能直接退出，请先转让队长或解散战队。")
    membership.delete()
    on_team_changed(team, author=user)


def remove_member(*, team, actor, member_user) -> None:
    if not is_captain(team, actor) and not actor.is_superuser:
        raise TeamError("只有队长可以移除成员。")
    if member_user.pk == actor.pk:
        raise TeamError("不能移除自己。")
    membership = TeamMembership.objects.filter(team=team, user=member_user).first()
    if membership is None:
        raise TeamError("这个人不是战队成员。")
    membership.delete()
    from teams import notifications

    notifications.member_removed(team, member_user)
    on_team_changed(team, author=actor)


@transaction.atomic
def transfer_captain(*, team, actor, new_captain) -> None:
    """Hand the captaincy to an existing member (design 7.4)."""
    if not is_captain(team, actor) and not actor.is_superuser:
        raise TeamError("只有队长可以转让队长。")
    target = TeamMembership.objects.filter(team=team, user=new_captain).first()
    if target is None:
        raise TeamError("只能转让给现有成员。")
    if target.is_captain:
        raise TeamError("这位成员已经是队长了。")
    if captained_count(new_captain) >= max_captained():
        raise TeamError("对方担任队长的战队已达上限。")
    current = TeamMembership.objects.filter(team=team, role=TeamRole.CAPTAIN).first()
    if current is not None:
        current.role = TeamRole.MEMBER
        current.save(update_fields=["role"])
    target.role = TeamRole.CAPTAIN
    target.save(update_fields=["role"])
    transaction.on_commit(lambda: _after_transfer(team, new_captain, actor))


def _after_transfer(team, new_captain, actor):
    from teams import notifications

    notifications.captain_changed(team, new_captain)
    on_team_changed(team, author=actor)


def assign_captain(*, team, actor, new_captain) -> None:
    """Superuser rescue path when a captain's account is gone (design 7.4)."""
    if not actor.is_superuser:
        raise TeamError("只有超级管理员可以指定队长。")
    if not is_member(team, new_captain):
        TeamMembership.objects.create(team=team, user=new_captain, role=TeamRole.MEMBER)
    transfer_captain(team=team, actor=actor, new_captain=new_captain)


def disband_blockers(team) -> list[str]:
    """Reasons the team cannot be disbanded.

    M4 adds the real check: a team with a registration that is pending,
    awaiting upstream, or approved on a draft/published tournament must
    withdraw it first (design 7.5).
    """
    return []


@transaction.atomic
def disband_team(*, team, actor) -> Team:
    if not is_captain(team, actor) and not actor.is_superuser:
        raise TeamError("只有队长或超级管理员可以解散战队。")
    if team.is_disbanded:
        raise TeamError("战队已经解散了。")
    blockers = disband_blockers(team)
    if blockers:
        raise TeamError("；".join(blockers))
    members = [
        membership.user for membership in team.memberships.select_related("user")
    ]
    url = team.get_absolute_url()
    team.disbanded_at = timezone.now()
    team.save(update_fields=["disbanded_at"])
    team.memberships.all().delete()
    team.applications.filter(status=ApplicationStatus.PENDING).update(
        status=ApplicationStatus.CANCELLED,
        decided_at=timezone.now(),
        decision_note="战队已解散",
    )
    transaction.on_commit(lambda: _after_disband(team, members, url))
    return team


def _after_disband(team, members, url):
    from core import prerender
    from teams import notifications

    notifications.team_disbanded(team, members)
    prerender.request_removal(url)
    refresh_team_list()


def my_teams(user):
    return (
        TeamMembership.objects.filter(user=user, team__disbanded_at__isnull=True)
        .select_related("team")
        .order_by("-joined_at")
    )


def my_applications(user):
    return (
        TeamApplication.objects.filter(applicant=user)
        .select_related("team")
        .order_by("-created_at")
    )


def pending_applications(team):
    return (
        TeamApplication.objects.filter(team=team, status=ApplicationStatus.PENDING)
        .select_related("applicant")
        .order_by("created_at")
    )


def open_teams(recruiting_only=False):
    """Team list: one query, with the member count annotated (no N+1)."""
    from django.db.models import Count

    query = (
        active_teams()
        .select_related("logo")
        .annotate(members_total=Count("memberships"))
    )
    if recruiting_only:
        query = query.filter(is_recruiting=True)
    return query


def refresh_team_list() -> None:
    from core import prerender

    prerender.request_page("/teams/", kind="team_index")


def on_team_changed(team, author=None) -> None:
    """Static pages and the AI queue both follow team changes."""
    from core import prerender

    if not team.is_disbanded:
        prerender.request_page(team.get_absolute_url(), kind="team")
    refresh_team_list()
    _submit_moderation(
        target_type="team_name",
        target_id=team.pk,
        field="name",
        text=team.name,
        url=team.get_absolute_url(),
        author=author,
    )
    if team.description:
        _submit_moderation(
            target_type="team_description",
            target_id=team.pk,
            field="description",
            text=team.description,
            url=team.get_absolute_url(),
            author=author,
        )


def _submit_moderation(*, target_type, target_id, field, text, url, author):
    from moderation import services as moderation_services

    try:
        moderation_services.submit(
            target_type=target_type,
            target_id=target_id,
            field=field,
            text=text,
            url=url,
            author=author,
        )
    except Exception:  # noqa: BLE001 — moderation must never block the action
        logger.warning("送审失败 %s #%s", target_type, target_id, exc_info=True)


def clean_name(name: str) -> str:
    name = (name or "").strip()
    if len(name) < 2 or len(name) > 16:
        raise ValidationError("队名需要 2 到 16 个字符。")
    return name


def blocked_query() -> Q:
    """Placeholder so M4 can express "teams with live registrations"."""
    return Q(pk__in=[])
