"""Team business rules (design 7). Every guard lives here, not in the views."""

from __future__ import annotations

import logging

from django.db import IntegrityError, transaction
from django.db.models.functions import Lower
from django.utils import timezone

from teams.images import discard_logo
from teams.models import (
    ApplicationStatus,
    LeaveReason,
    Team,
    TeamAlumnus,
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


def teams_without_captain():
    """Design 3.7 (v6.60): teams still going whose captain's account is
    disabled, or which have no captain at all. Nobody can approve their
    applications or enter them for a tournament until an admin names one."""
    working = TeamMembership.objects.filter(
        role=TeamRole.CAPTAIN, user__is_active=True
    ).values("team_id")
    return Team.objects.filter(disbanded_at__isnull=True).exclude(pk__in=working)


def captained_teams(user) -> list:
    return list(
        Team.objects.filter(
            disbanded_at__isnull=True,
            memberships__user=user,
            memberships__role=TeamRole.CAPTAIN,
        ).order_by("name")
    )


def pause_recruiting(user) -> list:
    """Design 3.7 (v6.62): the account was stopped, so the teams it captains
    take no applications (``can_apply``); stop advertising them as recruiting.
    The next captain turns it back on."""
    from core import prerender

    paused = [team for team in captained_teams(user) if team.is_recruiting]
    for team in paused:
        team.is_recruiting = False
        team.save(update_fields=["is_recruiting", "updated_at"])
        prerender.request_page(team.get_absolute_url(), kind="team")
    if paused:
        refresh_team_list()
    return paused


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


NAME_TAKEN = "已经有同名的战队了，换一个队名吧。"


def create_blocker(user) -> str:
    """Why this person cannot found a team now, or "": the create page says
    so before the form is filled in (round 115 review)."""
    from accounts.permissions import can_use, feature_denied_message

    if not can_use(user, "team_create"):
        return feature_denied_message("team_create")
    if captained_count(user) >= max_captained():
        return f"每人最多同时担任 {max_captained()} 支战队的队长。"
    return ""


def create_team(
    *, user, name, description="", logo=None, is_recruiting=True, recruiting_roles=""
) -> Team:
    """Create a team; the creator becomes its captain (design 7.1)."""
    try:
        with transaction.atomic():
            # The checks inside the transaction (216, T5): two at once could
            # both pass「最多同时担任 N 支战队的队长」 and both insert.
            blocker = create_blocker(user)
            if blocker:
                raise TeamError(blocker)
            if name_taken(name):
                raise TeamError(NAME_TAKEN)
            team = Team.objects.create(
                name=name,
                description=description,
                logo=logo,
                is_recruiting=is_recruiting,
                recruiting_roles=recruiting_roles,
            )
            TeamMembership.objects.create(team=team, user=user, role=TeamRole.CAPTAIN)
    except IntegrityError as exc:
        # Someone took the name between the check and the insert.
        raise TeamError(NAME_TAKEN) from exc
    on_team_changed(team, author=user)
    return team


def update_team(
    *,
    team,
    user,
    name,
    description,
    logo,
    is_recruiting,
    recruiting_roles=None,
    member_contact=None,
) -> Team:
    if not is_captain(team, user) and not user.is_superuser:
        raise TeamError("只有队长可以修改战队资料。")
    if team.is_disbanded:
        raise TeamError("战队已解散。")
    if name_taken(name, exclude_pk=team.pk):
        raise TeamError(NAME_TAKEN)
    old_logo = team.logo
    team.name = name
    team.description = description
    team.logo = logo
    team.is_recruiting = is_recruiting
    if recruiting_roles is not None:
        team.recruiting_roles = recruiting_roles
    if member_contact is not None:
        team.member_contact = member_contact.strip()
    try:
        team.save()
    except IntegrityError as exc:
        raise TeamError(NAME_TAKEN) from exc
    if old_logo is not None and old_logo.pk != getattr(logo, "pk", None):
        # The replaced or removed logo's file and thumbnails go too (219).
        transaction.on_commit(lambda: discard_logo(old_logo))
    on_team_changed(team, author=user)
    return team


CAPTAIN_STOPPED = "这支战队的队长账号已停用，等管理员指定新队长后再申请。"


def can_apply(team, user) -> tuple[bool, str]:
    """All the conditions from design 7.3, with the reason to show."""
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
    # Design 3.7 (v6.61): the application would wait on someone who cannot
    # log in, and close itself after 14 days.
    if teams_without_captain().filter(pk=team.pk).exists():
        return False, CAPTAIN_STOPPED
    if lacks_game_account(user):
        return False, "请先在个人中心添加至少一个游戏 ID。"
    if TeamApplication.objects.filter(
        team=team, applicant=user, status=ApplicationStatus.PENDING
    ).exists():
        return False, "你对这支战队还有一条待审批的申请。"
    return True, ""


def lacks_game_account(user) -> bool:
    from accounts.models import GameAccount

    return bool(getattr(user, "is_authenticated", False)) and not (
        GameAccount.objects.filter(user=user).exists()
    )


@transaction.atomic
def apply_to_team(*, team, user, roles, message="") -> TeamApplication:
    # One transaction (216, T5): a double click sent two requests that both
    # passed「还有一条待审批的申请」 and the second hit the unique constraint,
    # a 500. Now the second waits for the first (IMMEDIATE, design 12.12)
    # and is refused by the check.
    allowed, reason = can_apply(team, user)
    if not allowed:
        raise TeamError(reason)
    if not any(roles.values()):
        raise TeamError("请至少选择一个意向位置。")
    try:
        with transaction.atomic():
            application = TeamApplication.objects.create(
                team=team,
                applicant=user,
                role_tank=bool(roles.get("tank")),
                role_damage=bool(roles.get("damage")),
                role_support=bool(roles.get("support")),
                message=message,
            )
    except IntegrityError as exc:
        raise TeamError("你对这支战队还有一条待审批的申请。") from exc
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


GONE_NOTE = "申请人的账号已注销或停用"


def approve_application(*, application, actor) -> TeamApplication:
    """Approve inside one write transaction, re-checking the limits (7.3).

    What serialises two approvals is the transaction itself: every write
    transaction here takes the whole-database lock up front (IMMEDIATE,
    design 12.12). ``select_for_update`` does nothing on SQLite; it stays for
    a database that has row locks (216, T9)."""
    with transaction.atomic():
        application = TeamApplication.objects.select_for_update().get(pk=application.pk)
        team = application.team
        if not is_captain(team, actor) and not actor.is_superuser:
            raise TeamError("只有队长可以审批入队申请。")
        if application.status != ApplicationStatus.PENDING:
            raise TeamError("这条申请已经处理过了。")
        if team.is_disbanded:
            raise TeamError("战队已解散。")
        gone = not application.applicant.is_active
        already_member = is_member(team, application.applicant)
        if gone:
            # Round 173: a deleted or disabled account cannot join; close it
            # here and say so once the transaction is done.
            application.status = ApplicationStatus.CANCELLED
            application.decided_by = actor
            application.decided_at = timezone.now()
            application.decision_note = GONE_NOTE
            application.save()
        elif already_member:
            # Close the stale application. Raising inside this block would roll
            # the cancellation back and leave it pending for ever (round 059).
            application.status = ApplicationStatus.CANCELLED
            application.decided_by = actor
            application.decided_at = timezone.now()
            application.decision_note = "申请人已经是成员"
            application.save()
        else:
            if is_full(team):
                raise TeamError("战队人数已满，无法通过。")
            TeamMembership.objects.create(
                team=team, user=application.applicant, role=TeamRole.MEMBER
            )
            _unretire(team, application.applicant)
            application.status = ApplicationStatus.APPROVED
            application.decided_by = actor
            application.decided_at = timezone.now()
            application.save()
            transaction.on_commit(lambda: _after_approval(application, team, actor))
    if gone:
        raise TeamError("申请人的账号已注销或停用，这条申请已关闭。")
    if already_member:
        raise TeamError("申请人已经是这支战队的成员了。")
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


# Design 7.3 (v6.36): a captain who has not answered in two weeks is not
# going to; the applicant hears so and can look elsewhere.
STALE_APPLICATION_DAYS = 14
STALE_NOTE = f"队长 {STALE_APPLICATION_DAYS} 天没有处理，申请自动关闭"


def stale_applications(now=None):
    cutoff = (now or timezone.now()) - timezone.timedelta(days=STALE_APPLICATION_DAYS)
    return TeamApplication.objects.filter(
        status=ApplicationStatus.PENDING, created_at__lt=cutoff
    ).select_related("team", "applicant")


REMIND_CAPTAIN_DAYS = 7


def remind_captains(now=None) -> int:
    """Design 7.3 (v6.39): a week in, one letter per team listing what still
    waits; each application is mentioned once. Returns the letters sent."""
    from teams import notifications

    now = now or timezone.now()
    cutoff = now - timezone.timedelta(days=REMIND_CAPTAIN_DAYS)
    waiting = (
        TeamApplication.objects.filter(
            status=ApplicationStatus.PENDING,
            created_at__lt=cutoff,
            captain_reminded_at__isnull=True,
            team__disbanded_at__isnull=True,
            applicant__is_active=True,
        )
        .select_related("team", "applicant")
        .order_by("team_id", "created_at")
    )
    by_team: dict[int, list] = {}
    for application in waiting:
        by_team.setdefault(application.team_id, []).append(application)
    sent = 0
    for applications in by_team.values():
        team = applications[0].team
        captain = team.captain()
        if captain is not None and captain.is_active and captain.email:
            notifications.applications_waiting(team, applications, captain)
            sent += 1
        TeamApplication.objects.filter(pk__in=[a.pk for a in applications]).update(
            captain_reminded_at=now
        )
    return sent


def close_stale_applications(now=None) -> int:
    """Run nightly by ``cleanup_old_data``; each applicant gets a letter."""
    from teams import notifications

    closed = 0
    for application in stale_applications(now):
        application.status = ApplicationStatus.CANCELLED
        application.decided_at = now or timezone.now()
        application.decision_note = STALE_NOTE
        application.save(update_fields=["status", "decided_at", "decision_note"])
        if application.applicant.is_active:
            notifications.application_expired(application)
        closed += 1
    return closed


def leave_team(*, team, user) -> None:
    membership = TeamMembership.objects.filter(team=team, user=user).first()
    if membership is None:
        raise TeamError("你不是这支战队的成员。")
    if membership.is_captain:
        raise TeamError("队长不能直接退出，请先转让队长或解散战队。")
    _retire(membership, LeaveReason.LEFT)
    membership.delete()
    from teams import notifications

    notifications.member_left(team, user)
    on_team_changed(team, author=user)


def leave_all_teams(user) -> None:
    """Account deletion (design 3.8): leave every team, drop pending applications.

    Callers check captaincy first; a captain has to hand over or disband.
    """
    for membership in list(user.team_memberships.select_related("team")):
        team = membership.team
        membership.delete()
        on_team_changed(team)
    # Deleting an account takes its 退役 records too (design-details 5.4).
    for alumnus in list(user.team_alumni.select_related("team")):
        alumnus.delete()
        on_team_changed(alumnus.team)
    user.team_applications.filter(status=ApplicationStatus.PENDING).update(
        status=ApplicationStatus.CANCELLED, decided_at=timezone.now()
    )


def remove_member(*, team, actor, member_user) -> None:
    if not is_captain(team, actor) and not actor.is_superuser:
        raise TeamError("只有队长可以移除成员。")
    if member_user.pk == actor.pk:
        raise TeamError("不能移除自己。")
    membership = TeamMembership.objects.filter(team=team, user=member_user).first()
    if membership is None:
        raise TeamError("这个人不是战队成员。")
    if membership.is_captain:
        # A superuser could remove the captain and leave the team with none
        # (216). Hand the captaincy over first (「指定队长」).
        raise TeamError("不能移除队长，先把队长转给别人。")
    _retire(membership, LeaveReason.REMOVED)
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
    if not new_captain.is_active:
        # Same guard as assign_captain (213, T2): a stopped account as
        # captain deadlocks the team (nobody can apply, a superuser must
        # step in).
        raise TeamError("这个账号已停用，不能当队长。")
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


@transaction.atomic
def assign_captain(*, team, actor, new_captain) -> None:
    """Superuser rescue path when a captain's account is gone (design 7.4).

    One transaction (216, T4): the person used to join the team first and
    stay on it when the transfer was then refused (already captain of the
    most teams one may lead)."""
    if not actor.is_superuser:
        raise TeamError("只有超级管理员可以指定队长。")
    if team.is_disbanded:  # round 115
        raise TeamError("战队已经解散了，不能再指定队长。")
    if not new_captain.is_active:
        raise TeamError("这个账号已停用，不能当队长。")
    if not is_member(team, new_captain):
        if is_full(team):
            raise TeamError("战队人数已满，先移除一名成员，或者从现有成员里指定。")
        TeamMembership.objects.create(team=team, user=new_captain, role=TeamRole.MEMBER)
        _unretire(team, new_captain)
    transfer_captain(team=team, actor=actor, new_captain=new_captain)


def disband_blockers(team) -> list[str]:
    """Live registrations stop a disband, for captains and superusers (7.5).

    Live: pending or approved, on a tournament that is still a draft or
    published. The comment here used to say M4 would add
    this; it returned an empty list until round 061.
    """
    from tournaments.models import ACTIVE_STATUSES, TournamentStatus

    live = (
        team.registrations.filter(
            status__in=ACTIVE_STATUSES,
            tournament__status__in=[
                TournamentStatus.DRAFT,
                TournamentStatus.PUBLISHED,
            ],
        )
        .select_related("tournament")
        .order_by("tournament__registration_closes_at")
    )
    return [
        f"战队还在赛事「{registration.tournament.title}」的报名里，请先撤回报名。"
        for registration in live
    ]


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
    from accounts.services import with_avatars

    return with_avatars(
        TeamApplication.objects.filter(
            team=team, status=ApplicationStatus.PENDING, applicant__is_active=True
        )
        .select_related("applicant")
        .order_by("created_at"),
        "applicant__",
    )


def team_totals(limit=None) -> dict:
    """How many active teams, how many recruit, and how many each position
    could join now (design 7.6, v6.35: ``role_tank`` …), in one query."""
    from django.db.models import Count, Q

    from accounts.roles import ROLE_ORDER

    limit = limit or max_members()
    open_now = Q(is_recruiting=True, members_total__lt=limit)
    return (
        active_teams()
        .annotate(members_total=Count("memberships"))
        .aggregate(
            team_total=Count("id"),
            recruiting_total=Count("id", filter=Q(is_recruiting=True)),
            **{
                f"role_{role}": Count("id", filter=open_now & _wants(role))
                for role in ROLE_ORDER
            },
        )
    )


def open_teams(recruiting_only=False, role="", limit=None):
    """Team list: one query, with the member count annotated (no N+1).

    ``role`` (design 7.6, v6.35): only teams one could apply to now as that
    position: recruiting, not full, asking for it or for no one position.
    """
    from django.db.models import Count

    query = (
        active_teams()
        .select_related("logo")
        .annotate(members_total=Count("memberships"))
    )
    if recruiting_only or role:
        query = query.filter(is_recruiting=True)
    if role:
        query = query.filter(_wants(role), members_total__lt=limit or max_members())
    return query


def _wants(role):
    from django.db.models import Q

    return Q(recruiting_roles="") | Q(recruiting_roles__contains=role)


def refresh_team_list() -> None:
    from core import prerender

    prerender.request_page("/teams/", kind="team_index")
    # The homepage shows the newest teams (round 065).
    prerender.request_page("/", kind="home")
    # The member showcase lists everyone's teams (round 066).
    prerender.request_page("/members/", kind="members")


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


# --- 退役成员 (design-details 5.4, v5.2) ------------------------------------------


def _retire(membership, reason) -> None:
    """Keep a leaving member on the team page as 退役."""
    TeamAlumnus.objects.update_or_create(
        team_id=membership.team_id,
        user_id=membership.user_id,
        defaults={
            "role": membership.role,
            "joined_at": membership.joined_at,
            "left_at": timezone.now(),
            "reason": reason,
        },
    )


def _unretire(team, user) -> None:
    """Back on the roster: one person is not both 现役 and 退役."""
    TeamAlumnus.objects.filter(team=team, user=user).delete()


def can_remove_alumnus(alumnus, actor) -> bool:
    if not actor.is_authenticated:
        return False
    return (
        actor.pk == alumnus.user_id
        or actor.is_superuser
        or is_captain(alumnus.team, actor)
    )


def remove_alumnus(*, alumnus, actor) -> None:
    """The person or the captain takes a record off the list (5.4)."""
    if not can_remove_alumnus(alumnus, actor):
        raise TeamError("只有本人或队长可以去掉这条记录。")
    team = alumnus.team
    alumnus.delete()
    on_team_changed(team, author=actor)
