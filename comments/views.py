"""Comment endpoints (design 5.6, routes in 13.4). All responses are HTMX-friendly."""

from __future__ import annotations

from django.contrib import messages
from django.contrib.auth.views import redirect_to_login
from django.http import Http404, HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.views.decorators.http import require_GET, require_POST

from comments import services
from comments.models import Comment
from comments.rendering import section_context
from core.ratelimit import over_limit

COMMENT_LIMIT_MINUTE = 3
COMMENT_LIMIT_DAY = 100
DAY = 86400


def _page_or_404(page_pk):
    page = services.commentable_page(page_pk)
    if page is None:
        raise Http404("文章不存在或未发布。")
    return page


def _login_response(request):
    login_url = reverse("account_login")
    if getattr(request, "htmx", False):
        response = HttpResponse(status=200)
        response["HX-Redirect"] = login_url
        return response
    return redirect_to_login(request.get_full_path(), login_url)


def _section_response(request, page, problems=()):
    """Re-render the interactive section, or bounce back to the article."""
    if getattr(request, "htmx", False):
        context = section_context(request, page, interactive=True)
        if problems:
            context["post_problems"] = list(problems)
            context["can_post"] = False
        return render(request, "comments/section.html", context)
    for problem in problems:
        messages.error(request, problem)
    return redirect(f"{page.get_url() or '/'}#comments")


def _too_many(user) -> bool:
    return over_limit(f"comment:m:{user.pk}", COMMENT_LIMIT_MINUTE, 60) or over_limit(
        f"comment:d:{user.pk}", COMMENT_LIMIT_DAY, DAY
    )


def _post(request, page, parent=None):
    if not request.user.is_authenticated:
        return _login_response(request)
    if _too_many(request.user):
        return _section_response(request, page, ["评论太频繁了，稍后再试"])
    try:
        services.create(
            page=page,
            author=request.user,
            body=request.POST.get("body", ""),
            parent=parent,
        )
    except services.CommentError as exc:
        return _section_response(request, page, exc.problems)
    if not getattr(request, "htmx", False):
        messages.success(request, "评论已发表。")
    return _section_response(request, page)


@require_POST
def create(request, page_pk):
    return _post(request, _page_or_404(page_pk))


@require_POST
def reply(request, pk):
    parent = get_object_or_404(Comment.objects.select_related("page"), pk=pk)
    page = _page_or_404(parent.page_id)
    return _post(request, page, parent=parent)


@require_GET
def more(request, page_pk):
    """The next page of top-level comments, for 「加载更多」 (design 5.6)."""
    page = _page_or_404(page_pk)
    interactive = request.user.is_authenticated
    context = section_context(
        request, page, interactive=interactive, page_number=request.GET.get("page")
    )
    return render(request, "comments/_more.html", context)


def _moderate(request, pk, action):
    if not request.user.is_authenticated:
        return _login_response(request)
    comment = get_object_or_404(Comment.objects.select_related("page"), pk=pk)
    try:
        action(comment=comment, actor=request.user)
    except services.CommentError as exc:
        return HttpResponse(str(exc), status=403)
    return _section_response(request, comment.page)


@require_POST
def hide(request, pk):
    return _moderate(request, pk, services.hide)


@require_POST
def unhide(request, pk):
    return _moderate(request, pk, services.unhide)
