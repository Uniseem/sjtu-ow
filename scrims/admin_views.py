"""Publishing, finishing and cancelling a scrim in the back office (design
9.1, 14.2; docs/admin.md 4.3). Moved out of wagtail_hooks in v7.0."""

from __future__ import annotations

from functools import wraps

from django.contrib import messages
from django.core.exceptions import PermissionDenied
from django.http import Http404
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse

from core import admin_log
from scrims import services
from scrims.models import Scrim

ACTIONS = {
    "publish": ("发布内战", services.publish),
    "finish": ("标记为已结束", services.finish),
}
LOG_ACTIONS = {"publish": "scrims.publish", "finish": "scrims.finish"}


def manager_required(view):
    @wraps(view)
    def wrapper(request, *args, **kwargs):
        if not services.can_manage(request.user):
            raise PermissionDenied("需要内战管理权限。")
        return view(request, *args, **kwargs)

    return wrapper


def _back(scrim) -> dict:
    return {
        "back_url": reverse("scrims:edit", args=[scrim.pk]),
        "back_label": scrim.title,
    }


@manager_required
def scrim_action(request, pk, action):
    if action not in ACTIONS:
        raise Http404("没有这个操作。")
    scrim = get_object_or_404(Scrim, pk=pk)
    label, handler = ACTIONS[action]
    if request.method == "POST":
        try:
            handler(scrim=scrim, actor=request.user)
        except services.ScrimError as exc:
            messages.error(request, str(exc))
        else:
            admin_log.record(scrim, LOG_ACTIONS[action], request.user)
            messages.success(request, f"「{scrim.title}」已{label[:2]}。")
            if action == "publish" and request.POST.get("announce"):
                _announce_after_publish(request, scrim)
        return redirect("scrims:index")
    return render(
        request,
        "scrims/admin/confirm.html",
        {
            "page_title": f"{label}：{scrim.title}",
            "scrim": scrim,
            "action_label": label,
            "announce": _announce_offer(scrim) if action == "publish" else None,
            **_back(scrim),
        },
    )


@manager_required
def scrim_cancel(request, pk):
    scrim = get_object_or_404(Scrim, pk=pk)
    if request.method == "POST":
        try:
            services.cancel_scrim(scrim=scrim, actor=request.user)
        except services.ScrimError as exc:
            messages.error(request, str(exc))
        else:
            admin_log.record(scrim, "scrims.cancel", request.user)
            messages.success(request, f"「{scrim.title}」已取消。")
        return redirect("scrims:index")
    return render(
        request,
        "scrims/admin/confirm.html",
        {
            "page_title": f"取消内战：{scrim.title}",
            "scrim": scrim,
            "action_label": "取消内战",
            **_back(scrim),
        },
    )


def _announce_offer(scrim) -> dict:
    """The 「同时通知全体成员」 box on the publish page (design 10.4)."""
    from core import services as core_services

    return {
        "count": core_services.recipient_count(scrim),
        "problem": core_services.announcement_problem("scrim", scrim, publishing=True),
    }


def _announce_after_publish(request, scrim) -> None:
    from core import services as core_services

    try:
        broadcast = core_services.announce(kind="scrim", obj=scrim, actor=request.user)
    except core_services.AnnouncementError as exc:
        messages.warning(request, f"没有通知全体成员：{exc}")
    else:
        messages.success(
            request, f"已开始通知全体成员（{broadcast.recipient_count} 人）。"
        )
