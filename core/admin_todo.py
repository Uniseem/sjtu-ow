"""「待办」 on the back office's first page (findings #24, round 118; docs/
admin.md 4.1).

Each staff role sees how many things wait for it and where to handle them;
rows with nothing waiting are left out. People who handle none of these
(say a plain member) get no block at all.
"""

from __future__ import annotations

from dataclasses import dataclass

from django.urls import reverse
from django.utils import timezone

FINISH_NUDGE_AFTER = timezone.timedelta(days=3)
MAIL_LOOKBACK = timezone.timedelta(days=7)
BACKUP_STALE = timezone.timedelta(hours=36)
AI_LOOKBACK = timezone.timedelta(hours=24)
FAILED_CALL = "调用失败："


@dataclass(frozen=True)
class Todo:
    """One line: what waits (a full sentence), where to handle it, and how
    many — a line with nothing waiting is not shown."""

    text: str
    url: str
    count: int = 1


# The count is shared with the 审核 → 报名 tab (backoffice.nav).


def pending_registrations() -> int:
    from tournaments.models import Registration, RegistrationStatus, TournamentStatus

    return (
        Registration.objects.filter(status=RegistrationStatus.PENDING)
        .exclude(tournament__status=TournamentStatus.CANCELLED)
        .count()
    )


def _tournament_rows(user) -> list[Todo]:
    from tournaments import services as tournament_services
    from tournaments.models import (
        IndividualSignup,
        Tournament,
        TournamentStatus,
    )

    if not tournament_services.can_manage(user):
        return []
    pending = pending_registrations()
    rows = [
        Todo(
            f"{pending} 份报名等待审核",
            reverse("registration_review_index") + "?status=pending",
            pending,
        )
    ]
    waiting = (
        IndividualSignup.objects.filter(
            registration__isnull=True, tournament__status=TournamentStatus.PUBLISHED
        )
        .values_list("tournament")
        .order_by()
    )
    counts: dict[int, int] = {}
    for (tournament_id,) in waiting:
        counts[tournament_id] = counts.get(tournament_id, 0) + 1
    for tournament in Tournament.objects.filter(pk__in=counts).order_by("title"):
        rows.append(
            Todo(
                f"「{tournament.title}」有 {counts[tournament.pk]} 人等待编队",
                reverse("tournament_teams_board", args=[tournament.pk]),
                counts[tournament.pk],
            )
        )
    # Design 14.1 (v6.37): a tournament may run for days, so it is never
    # finished by itself; three days after it started, ask.
    over = Tournament.objects.filter(
        status=TournamentStatus.PUBLISHED,
        starts_at__lt=timezone.now() - FINISH_NUDGE_AFTER,
    ).order_by("starts_at")
    for tournament in over:
        rows.append(
            Todo(
                f"「{tournament.title}」开赛已经 {FINISH_NUDGE_AFTER.days} 天以上，"
                "打完了的话在赛事列表的「更多」里标记已结束",
                reverse("tournaments:index"),
            )
        )
    return rows


def _scrim_rows(user) -> list[Todo]:
    from scrims import services as scrim_services
    from scrims.models import Scrim, ScrimStatus

    if not scrim_services.can_manage(user):
        return []
    now = timezone.now()
    unsplit = (
        Scrim.objects.filter(
            status=ScrimStatus.PUBLISHED, signup_closes_at__lte=now, starts_at__gt=now
        )
        .exclude(signups__team__in=["a", "b"])
        .order_by("starts_at")
    )
    return [
        Todo(
            f"「{scrim.title}」报名已截止，还没分队",
            reverse("scrim_split", args=[scrim.pk]),
        )
        for scrim in unsplit
    ]


def _attempt(args_kwargs) -> int:
    args = (args_kwargs or {}).get("args") or []
    if len(args) > 1:
        return int(args[1])
    return int(((args_kwargs or {}).get("kwargs") or {}).get("attempt", 0))


def mail_failures(now=None) -> tuple[int, str]:
    """Emails the worker gave up on after its last retry in the past week,
    and the last error (design 14.1, v6.43). A broken SMTP setting used to
    show nowhere: sign-up codes simply did not arrive."""
    from django_tasks.base import TaskResultStatus
    from django_tasks_db.models import DBTaskResult

    from core.tasks import MAIL_RETRY_DELAYS

    rows = (
        DBTaskResult.objects.filter(
            task_path="core.tasks.deliver_queued_email",
            status=TaskResultStatus.FAILED,
            finished_at__gte=(now or timezone.now()) - MAIL_LOOKBACK,
        )
        .order_by("-finished_at")
        .values_list("args_kwargs", "traceback")
    )
    given_up = [
        traceback
        for args_kwargs, traceback in rows
        if _attempt(args_kwargs) >= len(MAIL_RETRY_DELAYS)
    ]
    if not given_up:
        return 0, ""
    lines = (given_up[0] or "").strip().splitlines()
    return len(given_up), (lines[-1] if lines else "")[:120]


def backup_problems(now=None) -> list[str]:
    """Design 16.7 (v6.45): no fresh archive, or the last upload failed. The
    nightly job runs from cron; nobody reads its output."""
    from datetime import datetime

    from core.management.commands.backup import (
        backup_root,
        existing_backups,
        read_status,
    )

    now = now or timezone.now()
    root = backup_root()
    archives = existing_backups(root) if root.exists() else []
    problems = []
    if not archives:
        problems.append("还没有任何备份，每天夜里的备份定时任务可能没设好")
    else:
        newest = max(path.stat().st_mtime for path in archives)
        age = now - datetime.fromtimestamp(newest, tz=timezone.get_current_timezone())
        if age > BACKUP_STALE:
            hours = int(age.total_seconds() // 3600)
            problems.append(
                f"最近一次备份是 {hours} 小时前，每天夜里的备份定时任务可能没在跑"
            )
    status = read_status(root) if root.exists() else {}
    if status.get("offsite") == "failed":
        problems.append(f"最近一次备份的异地上传失败：{status.get('error', '')[:120]}")
    return problems


def ai_failures(now=None) -> tuple[int, str]:
    """Design 14.1 (v6.46): reviews the provider could not answer in the past
    day, and why. They land in the queue as 「无法判定」, looking like a content
    problem when the key or the service is broken."""
    from moderation.models import ModerationItem

    failed = ModerationItem.objects.filter(
        checked_at__gte=(now or timezone.now()) - AI_LOOKBACK,
        reason__startswith=FAILED_CALL,
    ).order_by("-checked_at")
    count = failed.count()
    last = failed.values_list("reason", flat=True).first() if count else ""
    return count, (last or "").removeprefix(FAILED_CALL)[:120]


def _site_rows(user) -> list[Todo]:
    from core.admin_setup import _settings_url
    from core.models import PrerenderedPage, SiteSettings

    if not user.is_superuser:
        return []
    failed = PrerenderedPage.objects.filter(
        status=PrerenderedPage.Status.FAILED
    ).count()
    rows = [
        Todo(
            f"{failed} 个静态页面生成失败",
            reverse("core_prerender_index") + "?status=failed",
            failed,
        )
    ]
    # Design 14.1 (v6.44): with the worker down nothing is sent or rebuilt,
    # while the site itself looks fine.
    from core.health import check_worker_heartbeat

    beating, detail = check_worker_heartbeat()
    if not beating:
        rows.append(
            Todo(
                f"后台任务（worker）没在运行：{detail}。邮件、提醒、静态页都停了，"
                "到服务器上看 worker 容器",
                "/healthz",
            )
        )
    # Design 3.7 (v6.60): a disabled captain leaves the team stuck.
    from teams.services import teams_without_captain

    stuck = list(teams_without_captain().order_by("name")[:2])
    if stuck:
        count = teams_without_captain().count()
        where = (
            reverse("team_assign_captain", args=[stuck[0].pk])
            if count == 1
            else reverse("teams:index") + "?captain=gone"
        )
        rows.append(
            Todo(
                f"{count} 支战队的队长账号已停用，没人能审批入队申请、为它报名，"
                "去指定新队长",
                where,
                count,
            )
        )
    calls, why = ai_failures()
    if calls:
        rows.append(
            Todo(
                f"AI 审核最近 24 小时有 {calls} 次调用失败（{why}），"
                "检查密钥和接口，在「审核 → 内容」页点「试一下」",
                reverse("moderation_index"),
                calls,
            )
        )
    for problem in backup_problems():
        rows.append(Todo(problem, ""))
    lost, error = mail_failures()
    if lost:
        rows.append(
            Todo(
                f"最近 {MAIL_LOOKBACK.days} 天有 {lost} 封邮件重试后仍没发出去"
                f"（{error}），检查全站设置里的 SMTP，先发一封测试邮件",
                _settings_url(SiteSettings.load()),
                lost,
            )
        )
    return rows


def has_duties(user) -> bool:
    """Whether this person handles any of the queues above; others (say a
    verified author) get no panel rather than a permanently empty one."""

    from moderation.admin_views import can_review
    from scrims import services as scrim_services
    from tournaments import services as tournament_services

    return bool(
        user.is_superuser
        or can_review(user)
        or tournament_services.can_manage(user)
        or scrim_services.can_manage(user)
    )


def todo_rows(user) -> list[Todo]:
    # v6.72–v6.73: AI findings come by mail, faces and articles go out at
    # once; nothing of theirs waits here any more.
    rows = _tournament_rows(user) + _scrim_rows(user) + _site_rows(user)
    return [row for row in rows if row.count]
