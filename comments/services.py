"""Comment rules (design 5.6): who may post, what a thread looks like, hiding."""

from __future__ import annotations

import logging

from django.core.paginator import Paginator
from django.db import transaction
from django.db.models import Q

from comments.models import MAX_BODY, Comment

logger = logging.getLogger(__name__)

FEATURE = "article_comment"
PAGE_SIZE = 20
GROUP_CONTENT = "内容编辑"
COMMENT_PERMISSIONS = ("view_comment", "change_comment")
NOT_SIGNED_IN = "请先登录"


class CommentError(Exception):
    def __init__(self, problems):
        if isinstance(problems, str):
            problems = [problems]
        self.problems = list(problems)
        super().__init__("；".join(self.problems))


def commentable_page(page_pk):
    """A live, public article, or None (design 5.6: nothing else takes comments)."""
    from content.models import ArticlePage

    try:
        pk = int(page_pk)
    except (TypeError, ValueError):
        return None
    return ArticlePage.objects.live().public().filter(pk=pk).first()


def can_moderate(user) -> bool:
    if not getattr(user, "is_authenticated", False) or not user.is_active:
        return False
    return user.is_superuser or user.has_perm("comments.change_comment")


def can_comment(user, page) -> list[str]:
    """Everything stopping this person from posting on this page."""
    from accounts.permissions import can_use, feature_denied_message

    if not getattr(user, "is_authenticated", False):
        return [NOT_SIGNED_IN]
    problems = []
    if not can_use(user, FEATURE):
        problems.append(feature_denied_message(FEATURE))
    if not page.comments_enabled:
        problems.append("这篇文章关闭了评论")
    return problems


@transaction.atomic
def create(*, page, author, body, parent=None) -> Comment:
    """Post a comment or a reply (design 5.6). Replies stay one level deep."""
    problems = can_comment(author, page)
    body = (body or "").strip()
    if not body:
        problems.append("评论不能为空")
    if len(body) > MAX_BODY:
        problems.append(f"评论最多 {MAX_BODY} 字")
    reply_to = None
    if parent is not None:
        if parent.page_id != page.pk:
            problems.append("回复的评论不在这篇文章里")
        elif not parent.visible:
            problems.append("这条评论已经不能回复了")
        else:
            reply_to = parent.author
            if parent.parent_id is not None:
                # A reply to a reply lands in the same thread (design 5.6).
                parent = parent.parent
    if problems:
        raise CommentError(problems)
    comment = Comment.objects.create(
        page=page, author=author, parent=parent, reply_to_user=reply_to, body=body
    )
    transaction.on_commit(lambda: _after_write(comment))
    return comment


def _after_write(comment) -> None:
    _submit_moderation(comment)
    refresh_page(comment.page)


def _submit_moderation(comment) -> None:
    """Design 5.5.1: every comment goes to the reviewer queue, text only."""
    from moderation.services import submit

    page = comment.page
    try:
        submit(
            target_type="comment",
            target_id=comment.pk,
            field="body",
            text=comment.body,
            url=f"{page.get_url() or ''}#{comment.anchor}",
            author=comment.author,
        )
    except Exception:  # noqa: BLE001 — review must never block a comment
        logger.warning("评论送审失败 #%s", comment.pk, exc_info=True)


def refresh_page(page) -> None:
    """Design 13.13.4: the comment list is printed on the static article page."""
    from core import prerender

    url = page.get_url()
    if page.live and url:
        prerender.request_page(url, kind="article")


@transaction.atomic
def hide(*, comment, actor) -> Comment:
    if not can_moderate(actor):
        raise CommentError("需要内容编辑权限")
    comment.is_hidden = True
    comment.save(update_fields=["is_hidden"])
    transaction.on_commit(lambda: refresh_page(comment.page))
    return comment


@transaction.atomic
def unhide(*, comment, actor) -> Comment:
    if not can_moderate(actor):
        raise CommentError("需要内容编辑权限")
    comment.is_hidden = False
    comment.save(update_fields=["is_hidden"])
    transaction.on_commit(lambda: refresh_page(comment.page))
    return comment


def thread(page, *, viewer=None, page_number=1) -> dict:
    """The page's comments, newest first, pinned on top, replies attached.

    Readers see visible comments only; a hidden top-level comment that still
    has visible replies stays as a bodiless placeholder so the thread reads
    on. Moderators see hidden comments marked as such.
    """
    moderator = can_moderate(viewer)
    base = page.comments.filter(is_deleted=False).select_related(
        "author", "reply_to_user"
    )
    top = base.filter(parent__isnull=True)
    if not moderator:
        top = top.filter(
            Q(is_hidden=False) | Q(replies__is_hidden=False, replies__is_deleted=False)
        ).distinct()
    top = top.order_by("-is_pinned", "-created_at", "-id")
    paginator = Paginator(top, PAGE_SIZE)
    current = paginator.get_page(page_number)
    ids = [comment.pk for comment in current]
    replies = base.filter(parent_id__in=ids)
    if not moderator:
        replies = replies.filter(is_hidden=False)
    by_parent: dict = {}
    for reply in replies.order_by("created_at", "id"):
        by_parent.setdefault(reply.parent_id, []).append(reply)
    items = [
        {"comment": comment, "replies": by_parent.get(comment.pk, [])}
        for comment in current
    ]
    return {
        "items": items,
        "number": current.number,
        "has_next": current.has_next(),
        "next_number": current.next_page_number() if current.has_next() else None,
        "total": paginator.count,
    }


def assign_comment_permissions() -> list[str]:
    """Content editors moderate comments (design 4.1, 14.1)."""
    from django.contrib.auth.models import Group, Permission

    permissions = list(
        Permission.objects.filter(
            content_type__app_label="comments", codename__in=COMMENT_PERMISSIONS
        )
    )
    granted = []
    group = Group.objects.filter(name=GROUP_CONTENT).first()
    if group is not None and permissions:
        group.permissions.add(*permissions)
        granted.append(group.name)
    return granted
