"""「通知全体成员」 in the admin (design 10.4, v6.19): a preview of the
letter and how many people get it, then one click."""

from __future__ import annotations

from django.contrib import messages
from django.core.exceptions import PermissionDenied
from django.http import Http404
from django.shortcuts import get_object_or_404, redirect, render

from core import services
from core.letters import text_of


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
            if broadcast.waits_for_publish:
                messages.success(
                    request,
                    f"已安排：文章上线时给开着活动通知的成员发「{broadcast.subject}」。",
                )
            else:
                messages.success(
                    request,
                    f"已开始给 {broadcast.recipient_count} 人发"
                    f"「{broadcast.subject}」，在后台逐封发出。",
                )
        return redirect(entry.back_url(obj))
    letter = entry.letter(obj, services.unsubscribe_url(request.user))
    return render(
        request,
        "core/admin/announce.html",
        {
            "page_title": "通知全体成员",
            "obj": obj,
            "subject": letter.subject,
            "preview": text_of(letter, request.user.nickname),
            "count": services.recipient_count(obj),
            "sjtu_only": getattr(obj, "sjtu_only", False),
            "problem": services.announcement_problem(kind, obj),
            "going_live_at": services.going_live_at(kind, obj),
            "back_url": entry.back_url(obj),
            "back_label": entry.label,
        },
    )
