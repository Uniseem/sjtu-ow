"""评论 (docs/admin.md 4.5): only 隐藏 and 置顶, straight from the list
(design 5.6). Nobody adds, deletes or rewrites a comment here."""

from __future__ import annotations

from django.contrib import messages
from django.core.exceptions import PermissionDenied
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.views.decorators.http import require_POST

from backoffice.nav import placed
from backoffice.views.common import paginate, safe_next, search_text
from comments import services
from comments.models import Comment

PER_PAGE = 50
ACTIONS = {
    "hide": (services.hide, "已隐藏这条评论。"),
    "unhide": (services.unhide, "已恢复这条评论。"),
    "pin": (services.pin, "已置顶，这篇文章原来置顶的评论取消了置顶。"),
    "unpin": (services.unpin, "已取消置顶。"),
}


@placed("review", "comments")
def comment_list(request):
    comments = Comment.objects.select_related("author", "page").order_by(
        "-created_at", "-pk"
    )
    query = search_text(request)
    if query:
        comments = comments.filter(body__icontains=query)
    shown = request.GET.get("show") or ""
    if shown == "hidden":
        comments = comments.filter(is_hidden=True)
    elif shown == "pinned":
        comments = comments.filter(is_pinned=True)
    page_obj, extra_query = paginate(request, comments, PER_PAGE)
    return render(
        request,
        "backoffice/review/comments.html",
        {
            "page_title": "评论",
            "page_obj": page_obj,
            "extra_query": extra_query,
            "query": query,
            "shown": shown,
            "here": request.get_full_path(),
        },
    )


@placed("review", "comments")
@require_POST
def comment_action(request, pk, action):
    if action not in ACTIONS:
        raise PermissionDenied("没有这个操作。")
    comment = get_object_or_404(Comment, pk=pk)
    handler, done = ACTIONS[action]
    try:
        handler(comment=comment, actor=request.user)
    except services.CommentError as exc:
        messages.error(request, str(exc))
    else:
        messages.success(request, done)
    return redirect(safe_next(request, reverse("comments:index")))
