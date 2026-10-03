"""「通知全体成员」 in the admin (design 10.4, v6.19): a preview of the
letter and how many people get it, then one click."""

from __future__ import annotations

from django.contrib import messages
from django.core.exceptions import PermissionDenied
from django.http import Http404
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse

from core import services
from core.letters import text_of

BACK = {"tournament": "tournaments:index", "scrim": "scrims:index"}


def announce_view(request, kind, pk):
    entry = services.kinds().get(kind)
    if entry is None:
        raise Http404("没有这类通知。")
    if not entry.can_send(request.user):
        raise PermissionDenied("需要这类活动的管理权限。")
    obj = get_object_or_404(entry.model, pk=pk)
    if request.method == "POST":
        try:
            broadcast = services.announce(kind=kind, obj=obj, actor=request.user)
        except services.AnnouncementError as exc:
            messages.error(request, str(exc))
        else:
            messages.success(
                request,
                f"已开始给 {broadcast.recipient_count} 人发「{broadcast.subject}」，"
                "在后台逐封发出。",
            )
        return redirect(BACK[kind])
    letter = entry.letter(obj, services.unsubscribe_url(request.user))
    return render(
        request,
        "core/admin/announce.html",
        {
            "page_title": "通知全体成员",
            "header_icon": "mail",
            "obj": obj,
            "subject": letter.subject,
            "preview": text_of(letter, request.user.nickname),
            "count": services.recipient_count(obj),
            "sjtu_only": getattr(obj, "sjtu_only", False),
            "problem": services.announcement_problem(kind, obj),
            "back_url": reverse(BACK[kind]),
            "breadcrumbs_items": [
                {"url": reverse("wagtailadmin_home"), "label": "首页"},
                {
                    "url": reverse(BACK[kind]),
                    "label": "赛事" if kind == "tournament" else "内战活动",
                },
                {"url": "", "label": "通知全体成员"},
            ],
        },
    )
