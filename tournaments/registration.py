"""Registration: the eight checks, the roster snapshot and the state machine.

Design 8.3 (submit), 8.4 (lock and sync) and 8.5 (status flow).
"""

from __future__ import annotations

import logging

from django.db import transaction
from django.utils import timezone

from tournaments.models import (
    ACTIVE_STATUSES,
    ActorType,
    Registration,
    RegistrationAction,
    RegistrationMember,
    RegistrationStatus,
    RegistrationStatusLog,
    ReviewMode,
    TournamentStatus,
)

logger = logging.getLogger(__name__)


class RegistrationError(Exception):
    """One or more problems to show the captain; ``problems`` lists them all.

    ``code`` lets the API map a failure onto the right HTTP status (design
    11.6.7): ``review_not_allowed`` means the actor may never act in this
    review mode, ``invalid_state`` means the transition is wrong right now,
    ``validation_error`` means the request itself was incomplete.
    """

    def __init__(self, problems, *, code="invalid_state"):
        if isinstance(problems, str):
            problems = [problems]
        self.problems = list(problems)
        self.code = code
        super().__init__("；".join(self.problems))


def team_members(team):
    return list(team.memberships.select_related("user").order_by("-role", "joined_at"))


def member_problems(*, tournament, user, is_captain=False):
    """Everything wrong with one member, for the pre-check on the form (8.3)."""
    from accounts.permissions import can_use
    from accounts.services import profile_gaps

    problems = []
    # Design 8.3 check 5: one message for a deactivated account and a blocked
    # feature alike, so the captain never learns why (round 059). can_use()
    # already says no for an inactive user.
    if not can_use(user, "tournament_register"):
        problems.append(f"{user.nickname} 暂时无法参加赛事报名")
    gaps = [label for label, _url, _hint in profile_gaps(user)]
    if gaps:
        problems.append(f"{user.nickname} 的资料不完整（缺少{'、'.join(gaps)}）")
    if tournament.sjtu_only and not user.is_sjtu:
        problems.append(f"该赛事仅限交大用户参加，{user.nickname} 不符合")
    return problems


def existing_roster_conflict(*, tournament, user, exclude_registration=None):
    """Design 8.3 check 8: the member is already on another team's roster."""
    query = RegistrationMember.objects.filter(
        tournament=tournament, user=user, is_active=True
    ).select_related("registration")
    if exclude_registration is not None:
        query = query.exclude(registration=exclude_registration)
    entry = query.first()
    if entry is None:
        return ""
    return f"{user.nickname} 已经在该赛事的战队「{entry.registration.team_name}」名单中"


def precheck(*, tournament, team, actor, exclude_registration=None):
    """Everything the captain should fix before submitting (design 8.3)."""
    from teams.services import is_captain as is_team_captain

    problems = []
    now = timezone.now()
    if tournament.status != TournamentStatus.PUBLISHED or not (
        tournament.registration_opens_at <= now <= tournament.registration_closes_at
    ):
        problems.append("当前不在报名时间内")
    if team.is_disbanded or not is_team_captain(team, actor):
        problems.append("只有队长可以为战队报名")

    members = team_members(team)
    count = len(members)
    if not (tournament.roster_min <= count <= tournament.roster_max):
        problems.append(
            f"该赛事要求 {tournament.roster_min} 到 {tournament.roster_max} 人，"
            f"你的战队现在有 {count} 人"
        )
    for membership in members:
        problems.extend(
            member_problems(
                tournament=tournament,
                user=membership.user,
                is_captain=membership.is_captain,
            )
        )
        conflict = existing_roster_conflict(
            tournament=tournament,
            user=membership.user,
            exclude_registration=exclude_registration,
        )
        if conflict:
            problems.append(conflict)
    return problems


def _resolve_accounts(members, selections):
    """Check 7: every chosen game ID belongs to that member (design 8.3)."""
    from accounts.models import GameAccount

    problems = []
    chosen = {}
    for membership in members:
        user = membership.user
        account_id = selections.get(str(user.pk)) or selections.get(user.pk)
        account = None
        if account_id:
            account = GameAccount.objects.filter(pk=account_id, user=user).first()
        if account is None:
            account = GameAccount.objects.filter(user=user).order_by("pk").first()
            if account_id:
                problems.append("游戏 ID 选择有误，请刷新页面重试")
        if account is None:
            problems.append(f"{user.nickname} 还没有填写游戏 ID")
        chosen[user.pk] = account
    return chosen, problems


def _write_roster(registration, members, chosen):
    registration.members.all().delete()
    rows = []
    for membership in members:
        user = membership.user
        account = chosen.get(user.pk)
        rows.append(
            RegistrationMember(
                registration=registration,
                tournament=registration.tournament,
                user=user,
                game_account=account,
                nickname=user.nickname,
                battletag=account.battletag if account else "",
                is_sjtu=user.is_sjtu,
                rank_tank=account.rank_tank if account else None,
                rank_damage=account.rank_damage if account else None,
                rank_support=account.rank_support if account else None,
                is_captain=membership.is_captain,
                is_active=registration.status in ACTIVE_STATUSES,
            )
        )
    RegistrationMember.objects.bulk_create(rows)
    return rows


def roster_snapshot(registration):
    return [
        {
            "nickname": member.nickname,
            "battletag": member.battletag,
            "is_sjtu": member.is_sjtu,
            "is_captain": member.is_captain,
            "rank_tank": member.rank_tank,
            "rank_damage": member.rank_damage,
            "rank_support": member.rank_support,
        }
        for member in registration.members.all()
    ]


def log(
    registration,
    *,
    action,
    from_status,
    to_status,
    actor_type,
    actor_user=None,
    note="",
    snapshot=False,
):
    RegistrationStatusLog.objects.create(
        registration=registration,
        action=action,
        from_status=from_status or "",
        to_status=to_status,
        actor_type=actor_type,
        actor_user=actor_user if getattr(actor_user, "pk", None) else None,
        roster_version=registration.roster_version,
        roster_snapshot=roster_snapshot(registration) if snapshot else None,
        note=note,
    )


@transaction.atomic
def submit(*, tournament, team, actor, selections) -> Registration:
    """First submit, resubmit and roster sync all go through here (design 8.3)."""
    registration = (
        Registration.objects.select_for_update()
        .filter(tournament=tournament, team=team)
        .first()
    )
    is_new = registration is None
    action = RegistrationAction.SUBMIT
    from_status = ""
    if not is_new:
        from_status = registration.status
        if registration.status in ACTIVE_STATUSES:
            action = RegistrationAction.SYNC_ROSTER
        else:
            action = RegistrationAction.RESUBMIT

    problems = precheck(
        tournament=tournament,
        team=team,
        actor=actor,
        exclude_registration=registration,
    )
    members = team_members(team)
    chosen, account_problems = _resolve_accounts(members, selections or {})
    problems.extend(account_problems)
    if problems:
        raise RegistrationError(problems)

    if is_new:
        registration = Registration(tournament=tournament, team=team)
    registration.team_name = team.name
    registration.status = RegistrationStatus.PENDING
    registration.submitted_by = actor
    registration.submitted_at = timezone.now()
    registration.status_note = ""
    if not is_new:
        registration.roster_version += 1
    registration.save()

    _write_roster(registration, members, chosen)
    _refresh_public_pages(registration, from_status, registration.status)
    log(
        registration,
        action=action,
        from_status=from_status,
        to_status=registration.status,
        actor_type=ActorType.CAPTAIN,
        actor_user=actor,
        snapshot=True,
    )
    transaction.on_commit(lambda: _after_submit(registration, action))
    return registration


# Design 11.8.1: which event each captain action produces.
SUBMIT_EVENTS = {
    RegistrationAction.SUBMIT: "registration.submitted",
    RegistrationAction.RESUBMIT: "registration.submitted",
    RegistrationAction.SYNC_ROSTER: "registration.roster_synced",
}


def _refresh_public_pages(registration, from_status, to_status) -> None:
    """Approval shows on the tournament page and the team's record (13.13.4)."""
    if RegistrationStatus.APPROVED not in (from_status, to_status):
        return
    from core import prerender

    prerender.request_page(
        registration.tournament.get_absolute_url(), kind="tournament"
    )
    prerender.request_page(registration.team.get_absolute_url(), kind="team")


def _after_submit(registration, action):
    from tournaments import notifications

    notifications.registration_submitted(registration, action)
    event = SUBMIT_EVENTS.get(action)
    if event:
        _send_event(registration, event, actor_type=ActorType.CAPTAIN)


def captain_can_change(registration, now=None) -> bool:
    """Captains may only act before registration closes (design 8.5)."""
    now = now or timezone.now()
    return now <= registration.tournament.registration_closes_at


def _set_status(
    registration,
    *,
    action,
    to_status,
    actor_type,
    actor_user=None,
    note="",
    snapshot=False,
):
    from_status = registration.status
    registration.status = to_status
    registration.status_note = note
    registration.save(update_fields=["status", "status_note", "updated_at"])
    # 已驳回和已撤回的名单不占名额（design 8.5）
    registration.members.update(is_active=to_status in ACTIVE_STATUSES)
    _refresh_public_pages(registration, from_status, to_status)
    log(
        registration,
        action=action,
        from_status=from_status,
        to_status=to_status,
        actor_type=actor_type,
        actor_user=actor_user,
        note=note,
        snapshot=snapshot,
    )
    transaction.on_commit(
        lambda: _after_status_change(
            registration, note, action, actor_type, from_status
        )
    )
    return registration


def _after_status_change(registration, note, action, actor_type, from_status):
    from tournaments import notifications

    notifications.registration_status_changed(registration, note)
    event = (
        "registration.withdrawn"
        if action == RegistrationAction.WITHDRAW
        else "registration.status_changed"
    )
    _send_event(registration, event, actor_type=actor_type, previous_status=from_status)


def _send_event(registration, event_type, *, actor_type, previous_status=None):
    """Hand the event to the webhook layer. Never break the request over it."""
    from integrations import webhooks

    try:
        webhooks.queue_registration_event(
            registration,
            event_type,
            actor_type=actor_type,
            previous_status=previous_status or None,
        )
    except Exception:  # noqa: BLE001 — a webhook must not fail the action
        logger.warning("Webhook 事件 %s 排队失败", event_type, exc_info=True)


@transaction.atomic
def withdraw(*, registration, actor) -> Registration:
    from teams.services import is_captain as is_team_captain

    if not is_team_captain(registration.team, actor):
        raise RegistrationError("只有队长可以撤回报名")
    if registration.status not in ACTIVE_STATUSES:
        raise RegistrationError("当前状态不能撤回")
    if not captain_can_change(registration):
        raise RegistrationError("报名已截止，不能再修改")
    return _set_status(
        registration,
        action=RegistrationAction.WITHDRAW,
        to_status=RegistrationStatus.WITHDRAWN,
        actor_type=ActorType.CAPTAIN,
        actor_user=actor,
    )


def local_review_allowed(tournament) -> bool:
    """Whether this site's admins may act at all (design 8.5)."""
    return tournament.review_mode in (ReviewMode.LOCAL, ReviewMode.TWO_STAGE)


def upstream_review_allowed(tournament) -> bool:
    """The mirror of :func:`local_review_allowed` for the upstream (design 8.5).

    In ``local`` mode the upstream must not change any status, even though it
    holds the ``registrations:review`` scope.
    """
    return tournament.review_mode in (ReviewMode.UPSTREAM, ReviewMode.TWO_STAGE)


def _guard_actor(tournament, actor_type):
    if actor_type == ActorType.ADMIN and not local_review_allowed(tournament):
        raise RegistrationError(
            "这项赛事由上游审核，本站不能改状态", code="review_not_allowed"
        )
    if actor_type == ActorType.UPSTREAM and not upstream_review_allowed(tournament):
        raise RegistrationError(
            "这项赛事由本站审核，上游不能改状态", code="review_not_allowed"
        )


@transaction.atomic
def approve(*, registration, actor, actor_type=ActorType.ADMIN) -> Registration:
    tournament = registration.tournament
    _guard_actor(tournament, actor_type)
    if registration.status == RegistrationStatus.AWAITING_UPSTREAM:
        if actor_type != ActorType.UPSTREAM:
            raise RegistrationError("这一步要由上游确认")
        to_status = RegistrationStatus.APPROVED
    elif registration.status == RegistrationStatus.PENDING:
        two_stage = tournament.review_mode == ReviewMode.TWO_STAGE
        if two_stage and actor_type == ActorType.UPSTREAM:
            # Two-stage means this site reviews first; the upstream only
            # confirms what is already "待上游确认" (design 8.5).
            raise RegistrationError("这一步要先由本站管理员审核")
        to_status = (
            RegistrationStatus.AWAITING_UPSTREAM
            if (two_stage and actor_type == ActorType.ADMIN)
            else RegistrationStatus.APPROVED
        )
    else:
        raise RegistrationError("当前状态不能通过")
    return _set_status(
        registration,
        action=RegistrationAction.APPROVE,
        to_status=to_status,
        actor_type=actor_type,
        actor_user=actor,
    )


@transaction.atomic
def reject(*, registration, actor, note, actor_type=ActorType.ADMIN) -> Registration:
    if not note or not note.strip():
        raise RegistrationError("驳回必须填写备注", code="validation_error")
    tournament = registration.tournament
    _guard_actor(tournament, actor_type)
    if registration.status == RegistrationStatus.APPROVED:
        action = RegistrationAction.REVOKE
        if actor_type == ActorType.ADMIN and tournament.review_mode != ReviewMode.LOCAL:
            raise RegistrationError("这项赛事的撤销通过由上游操作")
    elif registration.status in (
        RegistrationStatus.PENDING,
        RegistrationStatus.AWAITING_UPSTREAM,
    ):
        action = RegistrationAction.REJECT
        if (
            registration.status == RegistrationStatus.AWAITING_UPSTREAM
            and actor_type != ActorType.UPSTREAM
        ):
            raise RegistrationError("这一步要由上游操作")
    else:
        raise RegistrationError("当前状态不能驳回")
    return _set_status(
        registration,
        action=action,
        to_status=RegistrationStatus.REJECTED,
        actor_type=actor_type,
        actor_user=actor,
        note=note.strip()[:300],
    )


def roster_differs_from_team(registration) -> bool:
    """Design 8.4: prompt the captain when the team changed after locking."""
    roster = set(registration.members.values_list("user_id", flat=True))
    current = set(registration.team.memberships.values_list("user_id", flat=True))
    return roster != current


def visible_to(registration, user) -> bool:
    """Only the captain and the people on the roster (design 8.6)."""
    if not getattr(user, "is_authenticated", False):
        return False
    from teams.services import is_captain as is_team_captain

    if is_team_captain(registration.team, user):
        return True
    return registration.members.filter(user=user).exists()


def my_registrations(user):
    return (
        Registration.objects.filter(members__user=user)
        .select_related("tournament", "team")
        .distinct()
        .order_by("-submitted_at")
    )
