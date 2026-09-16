"""Scrim signup and reminders (design 9.1, 9.2)."""

from __future__ import annotations

import logging

from django.db import IntegrityError, transaction
from django.utils import timezone

from scrims.models import (
    FINISHED_VISIBLE_DAYS,
    RANK_FIELDS,
    ROLE_FIELDS,
    ROLE_REQUIREMENTS,
    Role,
    Scrim,
    ScrimSignup,
    ScrimStatus,
)

logger = logging.getLogger(__name__)


class ScrimError(Exception):
    """One or more problems to show the player; ``problems`` lists them all."""

    def __init__(self, problems):
        if isinstance(problems, str):
            problems = [problems]
        self.problems = list(problems)
        super().__init__("；".join(self.problems))


# --- visibility ----------------------------------------------------------------


def public_scrims(now=None):
    """Design 9.2: published scrims, plus the recently finished ones.

    Cancelled scrims keep their detail page but leave the list.
    """
    now = now or timezone.now()
    cutoff = now - timezone.timedelta(days=FINISHED_VISIBLE_DAYS)
    return (
        Scrim.objects.filter(status=ScrimStatus.PUBLISHED)
        | Scrim.objects.filter(status=ScrimStatus.FINISHED, starts_at__gte=cutoff)
    ).order_by("starts_at")


def visible_scrim(pk):
    """Design 9.2: drafts are a 404 — do not leak that they exist."""
    return Scrim.objects.filter(pk=pk).exclude(status=ScrimStatus.DRAFT).first()


def signup_counts(scrim) -> dict:
    """Design 9.2: the totals shown on the detail page."""
    signups = scrim.signups.all()
    return {
        "total": len(signups),
        "tank": sum(1 for row in signups if row.role_tank),
        "damage": sum(1 for row in signups if row.role_damage),
        "support": sum(1 for row in signups if row.role_support),
    }


# --- eligibility ---------------------------------------------------------------


def signup_problems(*, scrim, user, now=None):
    """Every reason this player may not sign up (design 9.2)."""
    from accounts.permissions import can_use
    from accounts.services import profile_gaps

    now = now or timezone.now()
    problems = []
    if not user.is_authenticated:
        return ["请先登录"]
    if not user.is_active:
        problems.append("账号已停用")
    elif not can_use(user, "scrim_signup"):
        problems.append("你暂时无法报名内战")
    gaps = [label for label, _url, _hint in profile_gaps(user)]
    if gaps:
        problems.append(f"资料不完整（缺少{'、'.join(gaps)}）")
    if scrim.sjtu_only and not user.is_sjtu:
        problems.append("这场内战仅限交大用户参加")
    if scrim.status != ScrimStatus.PUBLISHED:
        problems.append("这场内战当前不接受报名")
    elif now > scrim.signup_deadline:
        problems.append("报名已截止")
    return problems


def role_problems(*, scrim, account, roles):
    """Design 9.2: the rank rules, which differ by format."""
    problems = []
    if not roles:
        problems.append("至少要勾选一个能打的位置")
        return problems
    labels = dict(Role.choices)
    if scrim.role_queue:
        # Every ticked role needs a rank on the chosen ID.
        missing = [
            labels[role]
            for role in roles
            if not getattr(account, RANK_FIELDS[role], None)
        ]
        if missing:
            problems.append(
                f"角色限定内战要求勾选的每个位置都填了段位，"
                f"这个游戏 ID 还缺：{'、'.join(missing)}"
            )
    else:
        # Open queue only needs one rank anywhere.
        if not any(getattr(account, field, None) for field in RANK_FIELDS.values()):
            problems.append("这个游戏 ID 一个位置的段位都没填")
    return problems


def _resolve_account(user, account_id):
    account = user.game_accounts.filter(pk=account_id).first()
    if account is None:
        raise ScrimError("请选择你自己的游戏 ID")
    return account


# --- signing up ----------------------------------------------------------------


@transaction.atomic
def sign_up(*, scrim, user, game_account_id, roles, now=None):
    """Create or update this player's signup (design 9.2)."""
    now = now or timezone.now()
    problems = signup_problems(scrim=scrim, user=user, now=now)
    account = None
    if not problems or "请先登录" not in problems:
        try:
            account = _resolve_account(user, game_account_id)
        except ScrimError as exc:
            problems.extend(exc.problems)
    if account is not None:
        problems.extend(role_problems(scrim=scrim, account=account, roles=roles))
    if problems:
        raise ScrimError(problems)

    signup = scrim.signups.filter(user=user).first()
    is_new = signup is None
    if is_new:
        signup = ScrimSignup(scrim=scrim, user=user)
    was_placed = bool(signup.team) if not is_new else False
    changed_account = not is_new and signup.game_account_id != account.pk
    signup.game_account = account
    for role, field in ROLE_FIELDS.items():
        setattr(signup, field, role in roles)
    if changed_account:
        # The split was made against the old ID's ranks, so it is stale.
        _clear_placement(signup)
    try:
        signup.save()
    except IntegrityError as exc:  # concurrent double submit
        raise ScrimError("你已经报名过这场内战了") from exc
    if was_placed and changed_account:
        _mark_teams_changed(scrim)
    return signup


@transaction.atomic
def cancel(*, scrim, user, now=None):
    """Design 9.2: cancelling pulls the player out of any generated split."""
    now = now or timezone.now()
    signup = scrim.signups.filter(user=user).first()
    if signup is None:
        raise ScrimError("你还没有报名这场内战")
    if now > scrim.signup_deadline:
        raise ScrimError("报名已截止，不能再取消")
    was_placed = signup.is_selected or bool(signup.team)
    signup.delete()
    if was_placed:
        _mark_teams_changed(scrim)
    return was_placed


def _clear_placement(signup) -> None:
    signup.is_selected = False
    signup.team = ""
    signup.assigned_role = ""
    signup.rating_used = None


def _mark_teams_changed(scrim) -> None:
    """Let the admin see that the saved split no longer matches the signups."""
    now = timezone.now()
    Scrim.objects.filter(pk=scrim.pk).update(roster_changed_at=now)
    scrim.roster_changed_at = now


def teams_are_stale(scrim) -> bool:
    """Design 9.2: "分队有变化" — someone left after the split was saved."""
    if scrim.teams_generated_at is None or scrim.roster_changed_at is None:
        return False
    return scrim.roster_changed_at > scrim.teams_generated_at


# --- admin actions -------------------------------------------------------------


def can_manage(user) -> bool:
    return bool(
        getattr(user, "is_superuser", False) or user.has_perm("scrims.change_scrim")
    )


@transaction.atomic
def publish(*, scrim, actor=None):
    if scrim.status == ScrimStatus.CANCELLED:
        raise ScrimError("已取消的内战不能再发布。")
    scrim.status = ScrimStatus.PUBLISHED
    fields = ["status", "updated_at"]
    if actor is not None and scrim.created_by is None:
        scrim.created_by = actor
        fields.append("created_by")
    scrim.save(update_fields=fields)
    schedule_reminder(scrim)
    return scrim


@transaction.atomic
def finish(*, scrim, actor=None):
    scrim.status = ScrimStatus.FINISHED
    scrim.save(update_fields=["status", "updated_at"])
    return scrim


@transaction.atomic
def cancel_scrim(*, scrim, actor=None):
    """Design 9.1: cancelling mails everyone who signed up."""
    if scrim.status == ScrimStatus.CANCELLED:
        raise ScrimError("这场内战已经取消了。")
    scrim.status = ScrimStatus.CANCELLED
    scrim.save(update_fields=["status", "updated_at"])
    transaction.on_commit(lambda: _notify_cancelled(scrim.pk))
    return scrim


def after_change(scrim, *, actor=None):
    """Re-arm the reminder whenever a published scrim is edited."""
    from core import prerender

    prerender.forget_targets()
    if scrim.status == ScrimStatus.PUBLISHED:
        schedule_reminder(scrim)
    _refresh_pages(scrim)


def _refresh_pages(scrim) -> None:
    from core import prerender

    prerender.request_page("/scrims/", kind="scrim_index")
    if scrim.is_public:
        prerender.request_page(f"/scrims/{scrim.pk}/", kind="scrim")
    else:
        prerender.request_removal(f"/scrims/{scrim.pk}/")


def _notify_cancelled(scrim_id) -> None:
    from scrims import notifications

    scrim = Scrim.objects.filter(pk=scrim_id).first()
    if scrim is not None:
        notifications.scrim_cancelled(scrim)


def reminder_offset_hours() -> int:
    from core.models import SiteSettings

    return int(getattr(SiteSettings.load(), "scrim_reminder_hours", 2) or 2)


def reminder_time(scrim):
    return scrim.starts_at - timezone.timedelta(hours=reminder_offset_hours())


def schedule_reminder(scrim) -> None:
    """Design 9.1: remind everyone two hours before it starts.

    Re-scheduling is safe: the task re-reads the scrim and checks both the
    time and ``reminder_sent_at``, so an outdated task does nothing.
    """
    from scrims.tasks import send_scrim_reminder

    run_at = reminder_time(scrim)
    scrim_id = scrim.pk

    def enqueue():
        if run_at <= timezone.now():
            send_scrim_reminder.enqueue(scrim_id)
        else:
            send_scrim_reminder.using(run_after=run_at).enqueue(scrim_id)

    transaction.on_commit(enqueue)


# --- team splitting (design 9.3-9.6) -------------------------------------------


def selected_signups(scrim):
    return list(
        scrim.signups.filter(is_selected=True).select_related("user", "game_account")
    )


def all_signups(scrim, *, order="created"):
    """Design 9.3: the admin may sort by signup time or by rank."""
    rows = list(scrim.signups.select_related("user", "game_account").all())
    if order == "rating":
        rows.sort(key=lambda row: (-(row.best_rating or 0), row.created_at))
    else:
        rows.sort(key=lambda row: (row.created_at, row.pk))
    return rows


@transaction.atomic
def set_selection(*, scrim, signup_ids):
    """Tick the players who are actually showing up tonight."""
    wanted = {int(value) for value in signup_ids}
    for signup in scrim.signups.all():
        should = signup.pk in wanted
        if signup.is_selected != should:
            signup.is_selected = should
            if not should:
                signup.team = ""
                signup.assigned_role = ""
                signup.rating_used = None
            signup.save(
                update_fields=["is_selected", "team", "assigned_role", "rating_used"]
            )
    return wanted


def generate_teams(scrim, *, rng=None):
    """Design 9.4. Raises :class:`~scrims.teaming.NoSolution` with a reason."""
    from scrims import teaming

    signups = selected_signups(scrim)
    players = teaming.players_from(signups, scrim)
    split = teaming.generate(players, scrim, rng=rng)
    return split, players


@transaction.atomic
def save_teams(*, scrim, placements):
    """Store one placement per signup: {signup_id: (team, role, rating)}.

    Design 9.5 lets the admin save a split that breaks the role counts, so
    nothing is validated here beyond the ids belonging to this scrim.
    """
    rows = {signup.pk: signup for signup in scrim.signups.all()}
    for signup_id, (team, role, rating) in placements.items():
        signup = rows.get(int(signup_id))
        if signup is None:
            continue
        signup.team = team or ""
        signup.assigned_role = role or ""
        signup.rating_used = rating
        signup.is_selected = bool(team)
        signup.save(
            update_fields=["team", "assigned_role", "rating_used", "is_selected"]
        )
    for signup in rows.values():
        if signup.pk not in {int(key) for key in placements}:
            if signup.team or signup.assigned_role:
                signup.team = ""
                signup.assigned_role = ""
                signup.rating_used = None
                signup.save(update_fields=["team", "assigned_role", "rating_used"])
    now = timezone.now()
    Scrim.objects.filter(pk=scrim.pk).update(
        teams_generated_at=now, roster_changed_at=None
    )
    scrim.teams_generated_at = now
    scrim.roster_changed_at = None
    return scrim


def placements_from_split(split, players, scrim):
    """Turn a freshly generated split into the shape ``save_teams`` wants."""
    from scrims.teaming import ratings_used

    used = ratings_used(split, players, scrim)
    placements = {}
    for team, assignment in (("a", split.a), ("b", split.b)):
        for role, ids in assignment.by_role.items():
            for signup_id in ids:
                placements[signup_id] = (team, role or "", used.get(signup_id))
    return placements


def team_rows(scrim):
    """Both teams as the admin page and the copy text need them."""
    rows = {"a": [], "b": []}
    for signup in scrim.signups.filter(team__in=["a", "b"]).select_related(
        "user", "game_account"
    ):
        rows[signup.team].append(signup)
    order = {Role.TANK: 0, Role.DAMAGE: 1, Role.SUPPORT: 2, "": 3}
    for side in rows.values():
        side.sort(key=lambda row: (order.get(row.assigned_role, 3), row.pk))
    return rows


def team_total(signups) -> int:
    return sum(signup.rating_used or 0 for signup in signups)


def role_counts(signups) -> dict:
    counts = {role: 0 for role in Role.values}
    for signup in signups:
        if signup.assigned_role in counts:
            counts[signup.assigned_role] += 1
    return counts


def requirement_problems(scrim, signups) -> list[str]:
    """Design 9.5: flag a split that breaks the format, but still allow saving."""
    if not scrim.role_queue:
        return []
    labels = dict(Role.choices)
    counts = role_counts(signups)
    wanted = ROLE_REQUIREMENTS[scrim.format]
    return [
        f"{labels[role]} {counts[role]} 人（需要 {needed} 人）"
        for role, needed in wanted.items()
        if counts[role] != needed
    ]


def copy_text(scrim) -> str:
    """Design 9.6: the block the admin pastes into the QQ group."""
    from accounts.ranks import format_rank

    rows = team_rows(scrim)
    when = timezone.localtime(scrim.starts_at).strftime("%Y-%m-%d %H:%M")
    lines = [f"【{scrim.title}】{when} · {scrim.get_format_display()}"]
    labels = dict(Role.choices)
    for team, name in (("a", "A 队"), ("b", "B 队")):
        side = rows[team]
        lines.append("")
        lines.append(f"{name}（总分 {team_total(side)}）")
        if scrim.role_queue:
            for role in (Role.TANK, Role.DAMAGE, Role.SUPPORT):
                members = [row for row in side if row.assigned_role == role]
                if not members:
                    continue
                entries = " / ".join(
                    f"{row.user.nickname} {row.game_account.battletag} "
                    f"{format_rank(row.rating_used)}"
                    for row in members
                )
                lines.append(f"{labels[role]}：{entries}")
        else:
            for row in side:
                lines.append(
                    f"{row.user.nickname} {row.game_account.battletag} "
                    f"{format_rank(row.rating_used)}"
                )
    return "\n".join(lines)
