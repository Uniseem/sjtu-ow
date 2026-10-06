"""Scrim signup and reminders (design 9.1, 9.2)."""

from __future__ import annotations

import logging
from datetime import timedelta

from django.db import IntegrityError, transaction
from django.utils import timezone

from core.converters import as_id
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

# Appendix C (v6.66): the homepage lists the next five scrims, however far
# off; until round 188 only the next 7 days, so one posted early never showed.
HOME_SCRIM_COUNT = 5


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


def signup_totals(scrims) -> dict:
    """Sign-ups per scrim, in one query, for slot meters on lists (5.2, 9.2)."""
    from django.db.models import Count

    rows = (
        ScrimSignup.objects.filter(scrim_id__in=[item.pk for item in scrims])
        .values("scrim_id")
        .annotate(n=Count("id"))
    )
    return {row["scrim_id"]: row["n"] for row in rows}


def upcoming_scrims(now=None, limit=HOME_SCRIM_COUNT):
    """The next published scrims not yet started, earliest first (design 5.2)."""
    now = now or timezone.now()
    return list(
        Scrim.objects.filter(
            status=ScrimStatus.PUBLISHED,
            starts_at__gte=now,
        ).order_by("starts_at")[:limit]
    )


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
    from accounts.permissions import can_use, feature_denied_message
    from accounts.services import profile_gaps

    now = now or timezone.now()
    problems = []
    if not user.is_authenticated:
        return ["请先登录"]
    if not user.is_active:
        problems.append("账号已停用")
    elif not can_use(user, "scrim_signup"):
        problems.append(feature_denied_message("scrim_signup"))  # 4.3.2, round 116
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
            if getattr(account, RANK_FIELDS[role], None) is None
        ]
        if missing:
            problems.append(
                f"角色限定内战要求勾选的每个位置都填了段位，"
                f"这个游戏 ID 还缺：{'、'.join(missing)}"
            )
    else:
        # Open queue only needs one rank anywhere.
        if all(getattr(account, field, None) is None for field in RANK_FIELDS.values()):
            problems.append("这个游戏 ID 一个位置的段位都没填")
    return problems


def _resolve_account(user, account_id):
    account = user.game_accounts.filter(pk=as_id(account_id)).first()
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
    was_placed = (signup.is_selected or bool(signup.team)) if not is_new else False
    changed_account = not is_new and signup.game_account_id != account.pk
    changed_roles = not is_new and any(
        getattr(signup, field) != (role in roles) for role, field in ROLE_FIELDS.items()
    )
    signup.game_account = account
    for role, field in ROLE_FIELDS.items():
        setattr(signup, field, role in roles)
    if changed_account or changed_roles:
        # The split was made against the old ID's ranks and roles (213, S2:
        # roles too — a player who drops a role breaks the saved split just
        # the same), so it is stale. Buffer players count as placed: their
        # is_selected is cleared here, and the admin must hear about it.
        _clear_placement(signup)
    try:
        signup.save()
    except IntegrityError as exc:  # concurrent double submit
        raise ScrimError("你已经报名过这场内战了") from exc
    if was_placed and (changed_account or changed_roles):
        _mark_teams_changed(scrim)
    _refresh_detail(scrim)
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
    _refresh_detail(scrim)
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


SCRIM_PERMISSIONS = ("add_scrim", "change_scrim", "delete_scrim", "view_scrim")


def assign_scrim_permissions() -> list[str]:
    """Scrim managers get the scrim model permissions (design 4.1).

    Missed in M6: until round 055 only superusers could manage scrims.
    """
    from django.contrib.auth.models import Group, Permission

    from accounts.services import GROUP_SCRIM

    permissions = list(
        Permission.objects.filter(
            content_type__app_label="scrims", codename__in=SCRIM_PERMISSIONS
        )
    )
    granted = []
    group = Group.objects.filter(name=GROUP_SCRIM).first()
    if group is not None and permissions:
        group.permissions.add(*permissions)
        granted.append(group.name)
    return granted


def can_delete(scrim) -> bool:
    """Only a draft nobody signed up for (round 115); otherwise cancel it.

    The back office list already counts signups (``signup_total``); asking
    the database again was one query per draft on the page (216, S10)."""
    if scrim.status != ScrimStatus.DRAFT:
        return False
    counted = getattr(scrim, "signup_total", None)
    if counted is not None:
        return counted == 0
    return not scrim.signups.exists()


# Design 9.1 (v6.30): a scrim is an evening; six hours after it starts it is
# over, whether or not anyone pressed 「标记已结束」.
FINISH_AFTER = timedelta(hours=6)


def finish_time(scrim):
    return scrim.starts_at + FINISH_AFTER


def schedule_auto_finish(scrim) -> None:
    """Re-scheduling is safe: the task re-reads the scrim and comes back
    later when the start moved, so one waiting no later is enough."""
    from core.tasks import enqueue_once
    from scrims.tasks import finish_past_scrim

    if scrim.starts_at is None:
        return
    run_at = finish_time(scrim)
    scrim_id = scrim.pk

    def enqueue():
        enqueue_once(finish_past_scrim, scrim_id, run_after=run_at, earlier_counts=True)

    transaction.on_commit(enqueue)


def missing(scrim) -> list[str]:
    """What a draft still lacks before it can go out (design 13.17, v7.10)."""
    gaps = []
    if not (scrim.title or "").strip():
        gaps.append("标题")
    if scrim.starts_at is None:
        gaps.append("开始时间")
    return gaps


@transaction.atomic
def publish(*, scrim, actor=None):
    # Status only moves forward (design 9.1, v7.16; 213/S3): a draft is the
    # only thing that can be published.
    if scrim.status == ScrimStatus.CANCELLED:
        raise ScrimError("已取消的内战不能再发布。")
    if scrim.status == ScrimStatus.FINISHED:
        raise ScrimError("已结束的内战不能再发布。")
    if scrim.status != ScrimStatus.DRAFT:
        raise ScrimError("这场内战已经发布了。")
    gaps = missing(scrim)
    if gaps:
        raise ScrimError(f"还没填好：{'、'.join(gaps)}。填好再发布。")
    scrim.status = ScrimStatus.PUBLISHED
    fields = ["status", "updated_at"]
    if actor is not None and scrim.created_by is None:
        scrim.created_by = actor
        fields.append("created_by")
    scrim.save(update_fields=fields)
    schedule_reminder(scrim)
    schedule_auto_finish(scrim)
    _status_changed(scrim)
    return scrim


@transaction.atomic
def finish(*, scrim, actor=None):
    # Only a published scrim can end (design 9.1, v7.16; 213/S3) — finishing
    # a draft would publish its blanks, finishing a cancelled one would put
    # it back on the list. Same rule as tournaments.services.finish.
    if scrim.status != ScrimStatus.PUBLISHED:
        raise ScrimError("只有已发布的内战可以标记为已结束。")
    scrim.status = ScrimStatus.FINISHED
    scrim.save(update_fields=["status", "updated_at"])
    _status_changed(scrim)
    return scrim


@transaction.atomic
def cancel_scrim(*, scrim, actor=None):
    """Design 9.1: cancelling mails everyone who signed up."""
    if scrim.status == ScrimStatus.CANCELLED:
        raise ScrimError("这场内战已经取消了。")
    if scrim.status == ScrimStatus.DRAFT and missing(scrim):
        # Cancelled is public; a half-filled draft would show its blanks.
        raise ScrimError("还没填好的草稿不用取消，直接删除。")
    scrim.status = ScrimStatus.CANCELLED
    scrim.save(update_fields=["status", "updated_at"])
    transaction.on_commit(lambda: _notify_cancelled(scrim.pk))
    _status_changed(scrim)
    return scrim


def after_change(scrim, *, actor=None):
    """Re-arm the reminder whenever a published scrim is edited."""
    from core import prerender

    prerender.forget_targets()
    if scrim.status == ScrimStatus.PUBLISHED:
        schedule_reminder(scrim)
        schedule_auto_finish(scrim)
    _refresh_pages(scrim)


def remove_signups_of(user) -> None:
    """Account deletion (design 3.8): drop the user's signups everywhere.

    Game IDs are PROTECTed by signups, so this has to run before they go.
    """
    for signup in list(user.scrim_signups.select_related("scrim")):
        scrim = signup.scrim
        was_placed = signup.is_selected or bool(signup.team)
        signup.delete()
        if was_placed:
            _mark_teams_changed(scrim)
        _refresh_detail(scrim)


def _refresh_detail(scrim) -> None:
    """Signups change the counts and the name list on the detail page, and the
    progress on the homepage's 近期安排 (13.13.4, v3.0).

    Requests for one page are merged 30 seconds apart, so a signup rush
    regenerates each once.
    """
    from core import prerender

    if scrim.is_public:
        prerender.request_page(f"/scrims/{scrim.pk}/", kind="scrim")
        prerender.request_page("/", kind="home")


def _status_changed(scrim) -> None:
    """The admin's publish / finish / cancel buttons (round 056).

    Only the edit form used to call after_change, so these buttons left the
    static list and detail pages stale until the nightly rebuild.
    """
    from core import prerender

    prerender.forget_targets()
    _refresh_pages(scrim)


def _refresh_pages(scrim) -> None:
    from core import prerender

    prerender.request_page("/scrims/", kind="scrim_index")
    # The homepage lists the next scrims (design 13.13.4).
    prerender.request_page("/", kind="home")
    schedule_home_refresh(scrim)
    if scrim.is_public:
        prerender.request_page(f"/scrims/{scrim.pk}/", kind="scrim")
    else:
        prerender.request_removal(f"/scrims/{scrim.pk}/")


def schedule_home_refresh(scrim) -> None:
    """Regenerate the pages whose content turns with the clock (design 13.13.4).

    Since round 076 the list, detail and homepage tickets say 「报名中」, so
    all three when sign-up closes and when the scrim starts (it then leaves the
    homepage). Until round 188 also the homepage when the scrim entered its
    7-day window; the homepage no longer has one.
    Stale tasks are harmless: they only regenerate the page from current data.
    """
    from core import prerender
    from core.tasks import enqueue_once, prerender_page

    if not prerender.is_enabled() or scrim.status != ScrimStatus.PUBLISHED:
        return
    now = timezone.now()
    status_pages = ["/", "/scrims/", f"/scrims/{scrim.pk}/"]
    runs = [(scrim.signup_deadline, status_pages), (scrim.starts_at, status_pages)]

    def enqueue():
        # Once per page and moment, however often it is saved (v7.10).
        for moment, paths in runs:
            for path in paths:
                if moment and moment > now:
                    enqueue_once(prerender_page, path, run_after=moment)

    transaction.on_commit(enqueue)


def _notify_cancelled(scrim_id) -> None:
    from scrims import notifications

    scrim = Scrim.objects.filter(pk=scrim_id).first()
    if scrim is not None:
        notifications.scrim_cancelled(scrim)


def note_time_change(scrim, old_starts_at) -> bool:
    """Design 9.1 (v6.34; v7.5): the admin moved a published scrim. The
    reminder goes out again; nobody is mailed on saving, the time the people
    signed up last knew is kept for 「通知报名的人」 (as tournaments do).
    Call before ``after_change``."""
    new = scrim.starts_at
    if (
        scrim.status != ScrimStatus.PUBLISHED
        or old_starts_at is None
        or new == old_starts_at
        or new <= timezone.now()
    ):
        return False
    told = scrim.moved_from or old_starts_at
    moved_from = None if told == new else told
    Scrim.objects.filter(pk=scrim.pk).update(
        reminder_sent_at=None, moved_from=moved_from
    )
    scrim.reminder_sent_at = None
    scrim.moved_from = moved_from
    return True


def community_group_url() -> str:
    """The community QQ group the split is posted to (design 9.2, v6.33)."""
    from core.models import SiteSettings

    return SiteSettings.load().qq_group_url or ""


def reminder_offset_hours() -> int:
    from core.models import SiteSettings

    return int(getattr(SiteSettings.load(), "scrim_reminder_hours", 2) or 2)


def reminder_time(scrim):
    return scrim.starts_at - timezone.timedelta(hours=reminder_offset_hours())


def schedule_reminder(scrim) -> None:
    """Design 9.1: remind everyone two hours before it starts.

    Re-scheduling is safe: the task re-reads the scrim and checks both the
    time and ``reminder_sent_at``, so an outdated task does nothing. One
    waiting task due no later is enough; saved inside the window, it goes
    out no sooner than ten minutes later (v7.10, as tournaments).
    """
    from core.tasks import enqueue_once, reminder_due
    from scrims.tasks import send_scrim_reminder

    if scrim.starts_at is None:
        return
    run_at = reminder_time(scrim)
    starts_at = scrim.starts_at
    scrim_id = scrim.pk

    def enqueue():
        due = reminder_due(run_at, starts_at)
        enqueue_once(send_scrim_reminder, scrim_id, run_after=due, earlier_counts=True)

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
    wanted = {as_id(value) for value in signup_ids} - {None}
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
    # Anyone the form did not place is in the buffer: still on tonight's board
    # (``is_selected`` stays set, so they are still listed there next time the
    # page loads) but on neither team, so they are not in the roster or the
    # copied result. Clearing is_selected here would make them vanish from the
    # board the moment you saved, which is the opposite of what a staging area
    # is for.
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
    when = (
        timezone.localtime(scrim.starts_at).strftime("%Y-%m-%d %H:%M")
        if scrim.starts_at
        else "时间未定"  # a draft still being filled in (v7.10)
    )
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
                    f"{row.user.nickname} {row.battletag} "
                    f"{format_rank(row.rating_used)}"
                    for row in members
                )
                lines.append(f"{labels[role]}：{entries}")
        else:
            for row in side:
                lines.append(
                    f"{row.user.nickname} {row.battletag} "
                    f"{format_rank(row.rating_used)}"
                )
    return "\n".join(lines)


# --- a player's own placement (design 9.2, v6.22) ---------------------------


def split_scrim_ids(scrim_ids) -> set[int]:
    """Which of these scrims have a saved split (anyone on team A or B)."""
    from scrims.models import ScrimSignup

    return set(
        ScrimSignup.objects.filter(scrim_id__in=scrim_ids, team__in=["a", "b"])
        .values_list("scrim_id", flat=True)
        .distinct()
    )


def placement(signup, *, has_split: bool | None = None) -> str:
    """What this player is told about their own place: 「A 队 · 坦克」,
    「替补」, 「这次没排上场」, or "" before there is a split. Only ever
    shown to the player (the public page has no split, design 9.2)."""
    from scrims.models import Role, Team

    scrim = signup.scrim
    if has_split is None:
        has_split = bool(split_scrim_ids([scrim.pk]))
    if not has_split:
        return ""
    if signup.team in (Team.A, Team.B):
        text = Team(signup.team).label
        if scrim.role_queue and signup.assigned_role:
            text += f" · {Role(signup.assigned_role).label}"
        return text
    if signup.is_selected:
        return "替补"
    return "这次没排上场"


# 「复制」 (design 14.2, v6.51): what a copy takes over. Only these, so the
# status, signups, reminders and notices of the old one never come along; a
# field added to the form later is left blank until it is decided here.
COPIED_FIELDS = ("title", "description", "format", "sjtu_only")
COPIED_TIMES = ("starts_at", "signup_closes_at")


def copy_for_new(scrim, now=None):
    """A new, unsaved scrim from this one, its times whole weeks later."""
    from core.services import copy_ahead

    return copy_ahead(scrim, COPIED_FIELDS, COPIED_TIMES, now)
