"""「通知全体成员」 and 「通知报名的人」 in the admin (design 10.4, v6.19;
v7.5): a preview of the letter, how many people get it and what went out
before, then one click. ``?to=participants`` is the second kind."""

from __future__ import annotations

from django.contrib import messages
from django.core.exceptions import PermissionDenied
from django.http import Http404
from django.shortcuts import get_object_or_404, redirect, render

from core import services
from core.letters import text_of


def _audience(request) -> str:
    asked = request.POST.get("to") or request.GET.get("to")
    return services.PARTICIPANTS if asked == "participants" else services.EVERYONE


def announce_view(request, kind, pk):
    entry = services.kinds().get(kind)
    if entry is None:
        raise Http404("没有这类通知。")
    if not entry.can_send(request.user):
        raise PermissionDenied("需要这类活动的管理权限。")
    obj = get_object_or_404(entry.model, pk=pk)
    audience = _audience(request)
    to_participants = audience == services.PARTICIPANTS
    if to_participants and entry.participants is None:
        raise Http404("这类内容没有报名的人。")
    if request.method == "POST":
        try:
            broadcast = services.announce(
                kind=kind,
                obj=obj,
                actor=request.user,
                audience=audience,
                note=request.POST.get("note", ""),
            )
        except services.AnnouncementError as exc:
            messages.error(request, str(exc))
        else:
            if broadcast.waits_for_publish:
                messages.success(
                    request,
                    f"已安排：文章上线时给开着活动通知的成员发「{broadcast.subject}」。",
                )
            else:
                who = "位报名的人" if to_participants else "人"
                messages.success(
                    request,
                    f"已开始给 {broadcast.recipient_count} {who}发"
                    f"「{broadcast.subject}」，在后台逐封发出。",
                )
        return redirect(entry.back_url(obj))
    sent = services.history(kind, obj)
    before = sent.count()
    moved_from = getattr(obj, "moved_from", None) if to_participants else None
    letter = services.compose(
        kind,
        obj,
        audience=audience,
        unsubscribe="" if to_participants else services.unsubscribe_url(request.user),
        moved_from=moved_from,
        before=before,
    )
    if to_participants:
        count = services.participant_count(kind, obj)
    else:
        count = services.recipient_count(obj)
    return render(
        request,
        "core/admin/announce.html",
        {
            "page_title": "通知报名的人" if to_participants else "通知全体成员",
            "obj": obj,
            "kind": kind,
            "to_participants": to_participants,
            "subject": letter.subject,
            "preview": text_of(letter, request.user.nickname),
            "count": count,
            "sjtu_only": getattr(obj, "sjtu_only", False),
            "problem": services.announcement_problem(kind, obj, audience=audience),
            "going_live_at": None
            if to_participants
            else services.going_live_at(kind, obj),
            "before": before,
            "last": sent.filter(waits_for_publish=False).first(),
            "moved_from": moved_from,
            "note_max": services.NOTE_MAX,
            "back_url": entry.back_url(obj),
            "back_label": entry.label,
        },
    )
