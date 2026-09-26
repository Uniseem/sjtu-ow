"""Registration: the eight checks, the roster snapshot and the state machine.

Design 8.3 (submit), 8.4 (lock and sync) and 8.5 (status flow). Round 067
removed the upstream review modes: this site's admins review, or the
tournament's ``auto_approve`` switch lets the system approve on submit.
"""

from __future__ import annotations

import logging

from django.db import IntegrityError, transaction
from django.utils import timezone

from tournaments.models import (
    ACTIVE_STATUSES,
    ActorType,
    IndividualSignup,
    Registration,
    RegistrationAction,
    RegistrationMember,
    RegistrationStatus,
    RegistrationStatusLog,
    TournamentStatus,
)

logger = logging.getLogger(__name__)

AUTO_APPROVE_NOTE = "自动通过"


class RegistrationError(Exception):
    """One or more problems to show the captain; ``problems`` lists them all."""

    def __init__(self, problems):
        if isinstance(problems, str):
            problems = [problems]
        self.problems = list(problems)
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
    if tournament.auto_approve:
        # Design 8.3: the switch lets the system approve inside the same
        # transaction. The status-changed mail is skipped for a system actor;
        # the "submitted" mail below already says the registration is approved.
        _set_status(
            registration,
            action=RegistrationAction.APPROVE,
            to_status=RegistrationStatus.APPROVED,
            actor_type=ActorType.SYSTEM,
            note=AUTO_APPROVE_NOTE,
        )
    transaction.on_commit(lambda: _after_submit(registration, action))
    return registration


def _refresh_public_pages(registration, from_status, to_status) -> None:
    """Approval shows on the tournament page, the team's record and the count
    in the homepage's 近期安排 (13.13.4)."""
    if RegistrationStatus.APPROVED not in (from_status, to_status):
        return
    from core import prerender

    prerender.request_page(
        registration.tournament.get_absolute_url(), kind="tournament"
    )
    prerender.request_page("/", kind="home")
    if registration.team_id:  # an ad-hoc team has no team page (8.8.2)
        prerender.request_page(registration.team.get_absolute_url(), kind="team")


def _after_submit(registration, action):
    from tournaments import notifications

    notifications.registration_submitted(registration, action)


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
    notify=True,
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
    if notify:
        transaction.on_commit(
            lambda: _after_status_change(registration, note, actor_type)
        )
    return registration


def _after_status_change(registration, note, actor_type):
    """Design 10.2: the captain hears about every change an admin makes.

    A system approval right after submit is not announced separately: the
    submit mail already carries the final status, and two mails for one
    action would only confuse (design 8.3).
    """
    if actor_type == ActorType.SYSTEM:
        return
    from tournaments import notifications

    notifications.registration_status_changed(registration, note)


@transaction.atomic
def withdraw(*, registration, actor) -> Registration:
    from teams.services import is_captain as is_team_captain

    if registration.team_id is None:
        raise RegistrationError("临时队伍由管理员解散，队员可以退出队伍")
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


@transaction.atomic
def approve(*, registration, actor) -> Registration:
    """Design 8.5 row 1: an admin passes a pending registration."""
    if registration.status != RegistrationStatus.PENDING:
        raise RegistrationError("当前状态不能通过")
    return _set_status(
        registration,
        action=RegistrationAction.APPROVE,
        to_status=RegistrationStatus.APPROVED,
        actor_type=ActorType.ADMIN,
        actor_user=actor,
    )


@transaction.atomic
def reject(*, registration, actor, note) -> Registration:
    """Design 8.5 rows 2 and 3: reject a pending one, or revoke an approval."""
    if not note or not note.strip():
        raise RegistrationError("驳回必须填写备注")
    if registration.status == RegistrationStatus.APPROVED:
        action = RegistrationAction.REVOKE
    elif registration.status == RegistrationStatus.PENDING:
        action = RegistrationAction.REJECT
    else:
        raise RegistrationError("当前状态不能驳回")
    return _set_status(
        registration,
        action=action,
        to_status=RegistrationStatus.REJECTED,
        actor_type=ActorType.ADMIN,
        actor_user=actor,
        note=note.strip()[:300],
    )


def roster_differs_from_team(registration) -> bool:
    """Design 8.4: prompt the captain when the team changed after locking."""
    if registration.team_id is None:
        return False
    roster = set(registration.members.values_list("user_id", flat=True))
    current = set(registration.team.memberships.values_list("user_id", flat=True))
    return roster != current


def visible_to(registration, user) -> bool:
    """Only the captain and the people on the roster (design 8.6)."""
    if not getattr(user, "is_authenticated", False):
        return False
    from teams.services import is_captain as is_team_captain

    if registration.team_id and is_team_captain(registration.team, user):
        return True
    return registration.members.filter(user=user).exists()


def my_registrations(user):
    return (
        Registration.objects.filter(members__user=user)
        .select_related("tournament", "team")
        .distinct()
        .order_by("-submitted_at")
    )


# --- individual signups: the pool (design 8.8.1) --------------------------------

ROLE_FIELDS = {"tank": "role_tank", "damage": "role_damage", "support": "role_support"}
NOT_SIGNED_IN = "请先登录"


def individual_problems(*, tournament, user, now=None) -> list[str]:
    """Everything stopping this person from signing up alone (design 8.8.1).

    Same checks as a team member gets in 8.3, plus the switch and the window.
    """
    if not getattr(user, "is_authenticated", False):
        return [NOT_SIGNED_IN]
    problems = []
    if not tournament.allow_individual_signup:
        problems.append("这项赛事不接受个人报名")
    if not tournament.registration_open(now):
        problems.append("当前不在报名时间内")
    problems.extend(member_problems(tournament=tournament, user=user))
    conflict = existing_roster_conflict(tournament=tournament, user=user)
    if conflict:
        problems.append(conflict)
    return problems


def individual_pool(tournament) -> list[IndividualSignup]:
    """People still waiting for a team (design 8.8.1); placed ones are listed
    with their team instead."""
    return list(
        tournament.individual_signups.filter(registration__isnull=True)
        .select_related("user")
        .order_by("created_at", "id")
    )


def pool_counts(pool) -> dict:
    return {
        "total": len(pool),
        "tank": sum(1 for entry in pool if entry.role_tank),
        "damage": sum(1 for entry in pool if entry.role_damage),
        "support": sum(1 for entry in pool if entry.role_support),
    }


def _own_account(user, game_account_id):
    try:
        return user.game_accounts.filter(pk=int(game_account_id)).first()
    except (TypeError, ValueError):
        return None


@transaction.atomic
def sign_up_individual(*, tournament, user, game_account_id, roles) -> IndividualSignup:
    """Create or update this person's pool entry (design 8.8.1)."""
    problems = individual_problems(tournament=tournament, user=user)
    account = None
    if NOT_SIGNED_IN not in problems:
        account = _own_account(user, game_account_id)
        if account is None:
            problems.append("请选择你自己的游戏 ID")
    roles = [role for role in roles if role in ROLE_FIELDS]
    if not roles:
        problems.append("至少要勾选一个能打的位置")
    if problems:
        raise RegistrationError(problems)

    signup = tournament.individual_signups.filter(user=user).first()
    if signup is not None and signup.is_placed:
        raise RegistrationError("你已经被编入队伍，要改动请联系赛事管理员")
    if signup is None:
        signup = IndividualSignup(tournament=tournament, user=user)
    signup.game_account = account
    for role, field in ROLE_FIELDS.items():
        setattr(signup, field, role in roles)
    try:
        signup.save()
    except IntegrityError as exc:  # concurrent double submit
        raise RegistrationError("你已经报名过这项赛事了") from exc
    _refresh_tournament_page(tournament)
    return signup


@transaction.atomic
def cancel_individual(*, tournament, user, now=None) -> None:
    """Leave the pool before the deadline (design 8.8.1)."""
    now = now or timezone.now()
    signup = tournament.individual_signups.filter(user=user).first()
    if signup is None:
        raise RegistrationError("你还没有个人报名这项赛事")
    if signup.is_placed:
        raise RegistrationError("你已经被编入队伍，要退出请在报名详情页操作")
    if now > tournament.registration_closes_at:
        raise RegistrationError("报名已截止，不能再取消")
    signup.delete()
    _refresh_tournament_page(tournament)


def _refresh_tournament_page(tournament) -> None:
    """Design 13.13.4: the pool is printed on the public tournament page."""
    if not tournament.is_listed:
        return
    from core import prerender

    prerender.request_page(tournament.get_absolute_url(), kind="tournament")


def my_individual_signups(user):
    return list(
        user.individual_signups.select_related("tournament", "registration").order_by(
            "-created_at"
        )
    )


# --- ad-hoc teams (design 8.8.2) ---------------------------------------------------

TEAM_NAME_MAX = 16
ADMIN_ADJUST_NOTE = "管理员调整"
AUTO_DISSOLVE_NOTE = "最后一名成员退出，队伍自动解散"


def adhoc_registrations(tournament) -> list[Registration]:
    """Live ad-hoc teams of a tournament, oldest first."""
    return list(
        tournament.registrations.filter(
            team__isnull=True, status__in=ACTIVE_STATUSES
        ).order_by("submitted_at", "id")
    )


def pool_entry_conflict(entry) -> str:
    """Why a pool entry cannot be placed: they joined a real team's roster."""
    return existing_roster_conflict(
        tournament=entry.tournament,
        user=entry.user,
        exclude_registration=entry.registration,
    )


def _name_problems(name, tournament, exclude=None) -> list[str]:
    if not name:
        return ["队伍要有名字"]
    if len(name) > TEAM_NAME_MAX:
        return [f"队名「{name[:TEAM_NAME_MAX]}…」超过 {TEAM_NAME_MAX} 字"]
    taken = tournament.registrations.filter(
        status__in=ACTIVE_STATUSES, team_name__iexact=name
    )
    if exclude is not None:
        taken = taken.exclude(pk=exclude.pk)
    if taken.exists():
        return [f"队名「{name}」在这项赛事里已经有了"]
    return []


def _write_adhoc_roster(registration, entries):
    """Snapshot pool entries as the roster (12.8.3), like _write_roster."""
    registration.members.all().delete()
    rows = []
    for entry in entries:
        account = entry.game_account
        user = entry.user
        rows.append(
            RegistrationMember(
                registration=registration,
                tournament=registration.tournament,
                user=user,
                game_account=account,
                nickname=user.nickname,
                battletag=account.battletag,
                is_sjtu=user.is_sjtu,
                rank_tank=account.rank_tank,
                rank_damage=account.rank_damage,
                rank_support=account.rank_support,
                is_captain=False,
                is_active=registration.status in ACTIVE_STATUSES,
            )
        )
    RegistrationMember.objects.bulk_create(rows)


def _dissolve(registration, *, actor, actor_type, note=""):
    """Members go back to the pool; the registration stops occupying places."""
    users = [row.user for row in registration.members.select_related("user")]
    IndividualSignup.objects.filter(registration=registration).update(registration=None)
    _set_status(
        registration,
        action=RegistrationAction.DISSOLVE,
        to_status=RegistrationStatus.WITHDRAWN,
        actor_type=actor_type,
        actor_user=actor,
        note=note,
        snapshot=True,
        notify=False,
    )
    return users


@transaction.atomic
def form_teams(*, tournament, actor, layout) -> dict:
    """Apply the board (design 8.8.2).

    ``layout`` is a list of ``{"registration_id", "name", "signup_ids"}``:
    one item per live ad-hoc team, plus one with ``registration_id=None``
    for a new team. Live teams missing from the layout lose everyone.
    Everything is validated first; nothing is written if anything is wrong.
    """
    live = {row.pk: row for row in adhoc_registrations(tournament)}
    entries = {
        row.pk: row
        for row in tournament.individual_signups.select_related("user", "game_account")
    }
    problems = []
    seen = set()
    plan = []
    mentioned = set()
    for team in layout:
        registration = None
        if team.get("registration_id"):
            registration = live.get(team["registration_id"])
            if registration is None:
                problems.append("有一支队伍已经不存在了，请刷新页面再试")
                continue
            mentioned.add(registration.pk)
        ids = []
        for signup_id in team.get("signup_ids", []):
            entry = entries.get(signup_id)
            if entry is None:
                problems.append("名单里有不属于这项赛事的人，请刷新页面再试")
                continue
            if signup_id in seen:
                problems.append(f"{entry.user.nickname} 被放进了两支队伍")
                continue
            seen.add(signup_id)
            ids.append(signup_id)
        name = (team.get("name") or "").strip()
        if not ids and registration is None:
            continue  # an empty new team is nothing
        if ids:
            if len(ids) > tournament.roster_max:
                problems.append(
                    f"「{name or '新队伍'}」有 {len(ids)} 人，"
                    f"超过上限 {tournament.roster_max}"
                )
            problems.extend(_name_problems(name, tournament, exclude=registration))
        plan.append((registration, name, ids))
    for registration in live.values():
        if registration.pk not in mentioned:
            plan.append((registration, registration.team_name, []))
    names = [name.lower() for _reg, name, ids in plan if ids]
    if len(names) != len(set(names)):
        problems.append("两支队伍不能同名")
    if problems:
        raise RegistrationError(problems)

    # Phase 1: take people off the teams they are leaving, so a move between
    # two teams never trips the one-active-roster-per-user constraint.
    desired = {}
    for registration, _name, ids in plan:
        if registration is not None:
            desired[registration.pk] = {entries[i].user_id for i in ids}
    before = {
        registration.pk: set(registration.members.values_list("user_id", flat=True))
        for registration in live.values()
    }
    returned = []
    result = {"created": 0, "updated": 0, "dissolved": 0, "returned": 0}
    for registration in live.values():
        keep = desired.get(registration.pk, set())
        leaving = [
            row
            for row in registration.members.select_related("user")
            if row.user_id not in keep
        ]
        if leaving:
            user_ids = [row.user_id for row in leaving]
            registration.members.filter(user_id__in=user_ids).delete()
            IndividualSignup.objects.filter(
                registration=registration, user_id__in=user_ids
            ).update(registration=None)
            returned.append((registration.team_name, [row.user for row in leaving]))
            result["returned"] += len(leaving)

    # Phase 2: check and write every team.
    formed = []
    now = timezone.now()
    for registration, name, ids in plan:
        chosen = [entries[i] for i in ids]
        if registration is not None and not chosen:
            _dissolve(
                registration,
                actor=actor,
                actor_type=ActorType.ADMIN,
                note=ADMIN_ADJUST_NOTE,
            )
            result["dissolved"] += 1
            continue
        member_issues = []
        for entry in chosen:
            member_issues.extend(
                member_problems(tournament=tournament, user=entry.user)
            )
            conflict = existing_roster_conflict(
                tournament=tournament,
                user=entry.user,
                exclude_registration=registration,
            )
            if conflict:
                member_issues.append(conflict)
        if member_issues:
            raise RegistrationError(member_issues)
        if registration is None:
            registration = Registration.objects.create(
                tournament=tournament,
                team=None,
                team_name=name,
                status=RegistrationStatus.APPROVED,
                submitted_by=actor,
                submitted_at=now,
            )
            _write_adhoc_roster(registration, chosen)
            IndividualSignup.objects.filter(pk__in=ids).update(
                registration=registration
            )
            log(
                registration,
                action=RegistrationAction.FORM_TEAM,
                from_status="",
                to_status=registration.status,
                actor_type=ActorType.ADMIN,
                actor_user=actor,
                snapshot=True,
            )
            result["created"] += 1
            formed.append((registration, [entry.user for entry in chosen]))
            continue
        current = before[registration.pk]
        wanted = {entry.user_id for entry in chosen}
        if current == wanted and registration.team_name == name:
            continue
        registration.team_name = name
        registration.roster_version += 1
        registration.save(update_fields=["team_name", "roster_version", "updated_at"])
        _write_adhoc_roster(registration, chosen)
        IndividualSignup.objects.filter(pk__in=ids).update(registration=registration)
        log(
            registration,
            action=RegistrationAction.SYNC_ROSTER,
            from_status=registration.status,
            to_status=registration.status,
            actor_type=ActorType.ADMIN,
            actor_user=actor,
            note=ADMIN_ADJUST_NOTE,
            snapshot=True,
        )
        result["updated"] += 1
        added = [entry.user for entry in chosen if entry.user_id not in current]
        if added:
            formed.append((registration, added))

    _refresh_tournament_page(tournament)
    transaction.on_commit(lambda: _after_board(tournament, formed, returned))
    return result


def _after_board(tournament, formed, returned):
    from tournaments import notifications_registration as mails

    for registration, users in formed:
        mails.adhoc_team_formed(registration, users)
    for team_name, users in returned:
        mails.adhoc_members_returned(tournament, team_name, users)


@transaction.atomic
def dissolve(*, registration, actor) -> None:
    """An admin dissolves an ad-hoc team; everyone goes back to the pool."""
    if registration.team_id is not None:
        raise RegistrationError("只有临时队伍能解散，战队报名请驳回")
    if registration.status not in ACTIVE_STATUSES:
        raise RegistrationError("这支队伍已经不在报名中")
    tournament = registration.tournament
    team_name = registration.team_name
    users = _dissolve(registration, actor=actor, actor_type=ActorType.ADMIN)
    _refresh_tournament_page(tournament)
    transaction.on_commit(lambda: _after_dissolve(tournament, team_name, users))


def _after_dissolve(tournament, team_name, users):
    from tournaments import notifications_registration as mails

    mails.adhoc_members_returned(tournament, team_name, users, dissolved=True)


@transaction.atomic
def leave(*, registration, user, enforce_deadline=True) -> bool:
    """A member leaves an ad-hoc team before the deadline (design 8.8.2).

    Returns True when the team dissolved because nobody was left. The
    member row is deleted, not flagged: ``_set_status`` rewrites
    ``is_active`` for every row, so a flag would come back to life.
    """
    if registration.team_id is not None:
        raise RegistrationError("战队报名由队长撤回，不能单独退出")
    if registration.status not in ACTIVE_STATUSES:
        raise RegistrationError("这支队伍已经不在报名中")
    row = registration.members.filter(user=user).first()
    if row is None:
        raise RegistrationError("你不在这支队伍的名单里")
    if enforce_deadline and not captain_can_change(registration):
        raise RegistrationError("报名已截止，不能再退出")
    row.delete()
    IndividualSignup.objects.filter(registration=registration, user=user).update(
        registration=None
    )
    dissolved = not registration.members.exists()
    if dissolved:
        _dissolve(
            registration,
            actor=user,
            actor_type=ActorType.SYSTEM,
            note=AUTO_DISSOLVE_NOTE,
        )
    else:
        registration.roster_version += 1
        registration.save(update_fields=["roster_version", "updated_at"])
        log(
            registration,
            action=RegistrationAction.MEMBER_LEFT,
            from_status=registration.status,
            to_status=registration.status,
            actor_type=ActorType.MEMBER,
            actor_user=user,
            snapshot=True,
        )
    _refresh_tournament_page(registration.tournament)
    transaction.on_commit(lambda: _after_leave(registration, user, dissolved))
    return dissolved


def _after_leave(registration, user, dissolved):
    from tournaments import notifications_registration as mails

    mails.adhoc_member_left(registration, user, dissolved=dissolved)
