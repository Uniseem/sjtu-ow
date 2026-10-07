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
LIKE_LIMIT_MINUTE = 60
DAY = 86400


def _page_or_404(page_pk):
    page = services.commentable_page(page_pk)
    if page is None:
        raise Http404("文章不存在或未发布。")
    return page


def _comment_and_page(pk):
    """The comment and its article, or 404 when the article is not live and
    public. Every endpoint that takes a comment number starts here (218, 217
    review 03-1): the number alone used to be enough to get the whole section
    of a taken-down or private article rendered back."""
    comment = get_object_or_404(Comment.objects.select_related("page"), pk=pk)
    return comment, _page_or_404(comment.page_id)


def _login_response(request):
    login_url = reverse("account_login")
    if getattr(request, "htmx", False):
        response = HttpResponse(status=200)
        response["HX-Redirect"] = login_url
        return response
    return redirect_to_login(request.get_full_path(), login_url)


def _section_response(request, page, problems=(), draft=""):
    """Re-render the interactive section, or bounce back to the article."""
    if getattr(request, "htmx", False):
        sort = request.POST.get("sort") or request.GET.get("sort")
        context = section_context(request, page, interactive=True, sort=sort)
        if problems:
            # A refused comment (too fast, too long) keeps the box and what was
            # typed in it; only a lasting reason (no right to comment) hides
            # the box, which section_context decides (round 116).
            context["post_problems"] = list(
                dict.fromkeys([*problems, *context["post_problems"]])
            )
            context["draft_body"] = draft
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
    # A top-level draft goes back into the box if the comment is refused.
    draft = request.POST.get("body", "") if parent is None else ""
    if _too_many(request.user):
        return _section_response(request, page, ["评论太频繁了，稍后再试"], draft)
    try:
        services.create(
            page=page,
            author=request.user,
            body=request.POST.get("body", ""),
            parent=parent,
        )
    except services.CommentError as exc:
        return _section_response(request, page, exc.problems, draft)
    if not getattr(request, "htmx", False):
        messages.success(request, "评论已发表。")
    return _section_response(request, page)


@require_POST
def create(request, page_pk):
    return _post(request, _page_or_404(page_pk))


@require_POST
def reply(request, pk):
    parent, page = _comment_and_page(pk)
    return _post(request, page, parent=parent)


@require_GET
def more(request, page_pk):
    """The next page of top-level comments, for 「加载更多」 (design 5.6)."""
    page = _page_or_404(page_pk)
    interactive = request.user.is_authenticated
    context = section_context(
        request,
        page,
        interactive=interactive,
        page_number=request.GET.get("page"),
        sort=request.GET.get("sort"),
    )
    return render(request, "comments/_more.html", context)


def _moderate(request, pk, action):
    if not request.user.is_authenticated:
        return _login_response(request)
    comment, page = _comment_and_page(pk)
    try:
        action(comment=comment, actor=request.user)
    except services.CommentError as exc:
        return HttpResponse(str(exc), status=403)
    return _section_response(request, page)


@require_POST
def hide(request, pk):
    return _moderate(request, pk, services.hide)


@require_POST
def unhide(request, pk):
    return _moderate(request, pk, services.unhide)


# --- likes, pins, the author's own edits (design 5.6, v1.9.1) ----------------------


def _act(request, pk, action, **kwargs):
    if not request.user.is_authenticated:
        return _login_response(request)
    comment, page = _comment_and_page(pk)
    try:
        action(comment=comment, **kwargs)
    except services.CommentError as exc:
        return _section_response(request, page, exc.problems)
    return _section_response(request, page)


@require_POST
def like(request, pk):
    if request.user.is_authenticated and over_limit(
        f"comment:like:{request.user.pk}", LIKE_LIMIT_MINUTE, 60
    ):
        _, page = _comment_and_page(pk)
        return _section_response(request, page, ["点赞太频繁了，稍后再试"])
    return _act(request, pk, services.toggle_like, user=request.user)


@require_POST
def edit(request, pk):
    if request.user.is_authenticated and _too_many(request.user):
        # Editing shares the posting limit (design 5.6, 213/S1).
        _, page = _comment_and_page(pk)
        return _section_response(request, page, ["编辑太频繁了，稍后再试"])
    return _act(
        request,
        pk,
        services.edit,
        actor=request.user,
        body=request.POST.get("body", ""),
    )


@require_POST
def delete(request, pk):
    return _act(request, pk, services.delete, actor=request.user)


@require_POST
def pin(request, pk):
    return _act(request, pk, services.pin, actor=request.user)


@require_POST
def unpin(request, pk):
    return _act(request, pk, services.unpin, actor=request.user)
