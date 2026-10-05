"""Publishing, finishing and cancelling a tournament in the back office
(design 8.1, 14.2; docs/admin.md 4.3). Moved out of wagtail_hooks in v7.0."""

from __future__ import annotations

from functools import wraps

from django.contrib import messages
from django.core.exceptions import PermissionDenied
from django.http import Http404
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse

from core import admin_log
from tournaments import services
from tournaments.models import Tournament

ACTIONS = {
    "publish": ("发布赛事", services.publish),
    "finish": ("标记为已结束", services.finish),
}
LOG_ACTIONS = {"publish": "tournaments.publish", "finish": "tournaments.finish"}


def manager_required(view):
    @wraps(view)
    def wrapper(request, *args, **kwargs):
        if not services.can_manage(request.user):
            raise PermissionDenied("需要赛事管理权限。")
        return view(request, *args, **kwargs)

    return wrapper


def _back(tournament) -> dict:
    return {
        "back_url": reverse("tournaments:edit", args=[tournament.pk]),
        "back_label": tournament.title,
    }


@manager_required
def tournament_action(request, pk, action):
    if action not in ACTIONS:
        raise Http404("没有这个操作。")
    tournament = get_object_or_404(Tournament, pk=pk)
    label, handler = ACTIONS[action]
    if request.method == "POST":
        try:
            handler(tournament=tournament, actor=request.user)
        except services.TournamentError as exc:
            messages.error(request, str(exc))
        else:
            admin_log.record(tournament, LOG_ACTIONS[action], request.user)
            messages.success(request, f"「{tournament.title}」已{label[:2]}。")
            if action == "publish" and request.POST.get("announce"):
                _announce_after_publish(request, tournament)
        return redirect("tournaments:index")
    return render(
        request,
        "tournaments/admin/confirm.html",
        {
            "page_title": f"{label}：{tournament.title}",
            "tournament": tournament,
            "action_label": label,
            "announce": _announce_offer(tournament) if action == "publish" else None,
            "needs_reason": False,
            **_back(tournament),
        },
    )


@manager_required
def tournament_cancel(request, pk):
    tournament = get_object_or_404(Tournament, pk=pk)
    if request.method == "POST":
        try:
            reason = request.POST.get("reason", "")[:300]
            services.cancel(tournament=tournament, actor=request.user, reason=reason)
        except services.TournamentError as exc:
            messages.error(request, str(exc))
        else:
            admin_log.record(
                tournament, "tournaments.cancel", request.user, reason=reason
            )
            messages.success(request, f"「{tournament.title}」已取消。")
        return redirect("tournaments:index")
    return render(
        request,
        "tournaments/admin/confirm.html",
        {
            "page_title": f"取消赛事：{tournament.title}",
            "tournament": tournament,
            "action_label": "取消赛事",
            "needs_reason": True,
            **_back(tournament),
        },
    )


def _announce_offer(tournament) -> dict:
    """The 「同时通知全体成员」 box on the publish page (design 10.4)."""
    from core import services as core_services

    return {
        "count": core_services.recipient_count(tournament),
        "problem": core_services.announcement_problem(
            "tournament", tournament, publishing=True
        ),
    }


def _announce_after_publish(request, tournament) -> None:
    from core import services as core_services

    try:
        broadcast = core_services.announce(
            kind="tournament", obj=tournament, actor=request.user
        )
    except core_services.AnnouncementError as exc:
        messages.warning(request, f"没有通知全体成员：{exc}")
    else:
        messages.success(
            request, f"已开始通知全体成员（{broadcast.recipient_count} 人）。"
        )
