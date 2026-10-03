"""「待办」 on the admin dashboard (findings #24, round 118).

Each staff role sees how many things wait for it and where to handle them;
rows with nothing waiting are left out. Pure submitters keep their own
「我的投稿」 panel (design 14.3) and never see this one.
"""

from __future__ import annotations

from dataclasses import dataclass

from django.urls import reverse
from django.utils import timezone
from wagtail.admin.ui.components import Component


@dataclass(frozen=True)
class Todo:
    """One line: what waits (a full sentence), where to handle it, and how
    many — a line with nothing waiting is not shown."""

    text: str
    url: str
    count: int = 1


def _review_rows(user) -> list[Todo]:
    from accounts.models import AvatarSubmission
    from moderation.admin_views import can_review
    from moderation.models import ModerationItem, Risk

    if not can_review(user):
        return []
    flagged = (
        ModerationItem.objects.exclude(risk=Risk.NONE)
        .filter(status=ModerationItem.Status.PENDING, checked_at__isnull=False)
        .count()
    )
    avatars = AvatarSubmission.objects.filter(
        status=AvatarSubmission.Status.PENDING
    ).count()
    return [
        Todo(f"{flagged} 条内容等待复核", reverse("moderation_index"), flagged),
        Todo(f"{avatars} 张头像等待审核", reverse("avatar_review"), avatars),
    ]


def _submission_rows(user) -> list[Todo]:
    """Article submissions whose current step this person may approve."""
    from wagtail.models import GroupApprovalTask, TaskState

    states = TaskState.objects.filter(status=TaskState.STATUS_IN_PROGRESS)
    if not user.is_superuser:
        tasks = GroupApprovalTask.objects.filter(groups__in=user.groups.all())
        states = states.filter(task__in=tasks)
    count = states.values("workflow_state").distinct().count()
    return [
        Todo(f"{count} 篇稿件等待审核", reverse("wagtailadmin_reports:workflow"), count)
    ]


def _tournament_rows(user) -> list[Todo]:
    from tournaments import services as tournament_services
    from tournaments.models import (
        IndividualSignup,
        Registration,
        RegistrationStatus,
        Tournament,
        TournamentStatus,
    )

    if not tournament_services.can_manage(user):
        return []
    pending = (
        Registration.objects.filter(status=RegistrationStatus.PENDING)
        .exclude(tournament__status=TournamentStatus.CANCELLED)
        .count()
    )
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


def _site_rows(user) -> list[Todo]:
    from core.models import PrerenderedPage

    if not user.is_superuser:
        return []
    failed = PrerenderedPage.objects.filter(
        status=PrerenderedPage.Status.FAILED
    ).count()
    return [
        Todo(
            f"{failed} 个静态页面生成失败",
            reverse("core_prerender_index") + "?status=failed",
            failed,
        )
    ]


def has_duties(user) -> bool:
    """Whether this person handles any of the queues above; others (say a
    verified author) get no panel rather than a permanently empty one."""
    from wagtail.models import GroupApprovalTask

    from moderation.admin_views import can_review
    from scrims import services as scrim_services
    from tournaments import services as tournament_services

    return bool(
        user.is_superuser
        or can_review(user)
        or tournament_services.can_manage(user)
        or scrim_services.can_manage(user)
        or GroupApprovalTask.objects.filter(
            active=True, groups__in=user.groups.all()
        ).exists()
    )


def todo_rows(user) -> list[Todo]:
    rows = (
        _review_rows(user)
        + _submission_rows(user)
        + _tournament_rows(user)
        + _scrim_rows(user)
        + _site_rows(user)
    )
    return [row for row in rows if row.count]


class TodoPanel(Component):
    name = "site_todo"
    template_name = "core/admin/todo_panel.html"
    order = 10

    def get_context_data(self, parent_context):
        request = parent_context["request"]
        return {"rows": todo_rows(request.user)}
