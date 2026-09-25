"""Comment rules (design 5.6): who may post, what a thread looks like, hiding."""

from __future__ import annotations

import logging

from django.core.paginator import Paginator
from django.db import transaction
from django.db.models import Count, Exists, F, OuterRef, Q
from django.utils import timezone

from comments.models import MAX_BODY, Comment, CommentLike

logger = logging.getLogger(__name__)

FEATURE = "article_comment"
PAGE_SIZE = 20
SORTS = ("new", "top")
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
    comment.is_pinned = False
    comment.save(update_fields=["is_hidden", "is_pinned"])
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


def thread(page, *, viewer=None, page_number=1, sort="new") -> dict:
    """The page's comments, pinned on top, newest or hottest first, replies attached.

    Readers see visible comments only; a hidden or deleted top-level comment
    that still has visible replies stays as a bodiless placeholder so the
    thread reads on. Moderators see hidden comments marked as such.
    """
    sort = sort if sort in SORTS else "new"
    moderator = can_moderate(viewer)
    base = page.comments.select_related("author", "reply_to_user")
    surviving = Comment.objects.filter(parent=OuterRef("pk"), is_deleted=False)
    if not moderator:
        surviving = surviving.filter(is_hidden=False)
    live_reply = Exists(surviving)
    top = base.filter(parent__isnull=True).annotate(has_live_reply=live_reply)
    if moderator:
        top = top.filter(Q(is_deleted=False) | Q(has_live_reply=True))
    else:
        top = top.filter(Q(is_hidden=False, is_deleted=False) | Q(has_live_reply=True))
    if sort == "top":
        top = top.annotate(
            reply_count=Count(
                "replies", filter=Q(replies__is_hidden=False, replies__is_deleted=False)
            )
        ).order_by("-is_pinned", "-like_count", "-reply_count", "-created_at", "-id")
    else:
        top = top.order_by("-is_pinned", "-created_at", "-id")
    paginator = Paginator(top, PAGE_SIZE)
    current = paginator.get_page(page_number)
    ids = [comment.pk for comment in current]
    replies = base.filter(parent_id__in=ids, is_deleted=False)
    if not moderator:
        replies = replies.filter(is_hidden=False)
    by_parent: dict = {}
    reply_ids = []
    for reply in replies.order_by("created_at", "id"):
        by_parent.setdefault(reply.parent_id, []).append(reply)
        reply_ids.append(reply.pk)
    liked = set()
    if getattr(viewer, "is_authenticated", False):
        liked = set(
            CommentLike.objects.filter(
                user=viewer, comment_id__in=ids + reply_ids
            ).values_list("comment_id", flat=True)
        )
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
        "sort": sort,
        "liked": liked,
    }


# --- likes, pins, the author's own edits (design 5.6, v1.9.1) ----------------------


@transaction.atomic
def toggle_like(*, comment, user) -> bool:
    """Like, or take the like back. Returns True when a like was added."""
    if not getattr(user, "is_authenticated", False):
        raise CommentError(NOT_SIGNED_IN)
    if not comment.visible:
        raise CommentError("这条评论不能点赞")
    like, created = CommentLike.objects.get_or_create(comment=comment, user=user)
    if created:
        Comment.objects.filter(pk=comment.pk).update(like_count=F("like_count") + 1)
    else:
        like.delete()
        Comment.objects.filter(pk=comment.pk, like_count__gt=0).update(
            like_count=F("like_count") - 1
        )
    comment.refresh_from_db(fields=["like_count"])
    transaction.on_commit(lambda: refresh_page(comment.page))
    return created


def pin_problem(comment, *, hidden=None) -> str | None:
    """Why this comment cannot be pinned, or None (design 5.6)."""
    if not comment.is_top_level:
        return "只能置顶顶层评论"
    hidden = comment.is_hidden if hidden is None else hidden
    if hidden or comment.is_deleted:
        return "这条评论不能置顶"
    return None


def release_pin(page, *, keep=None) -> None:
    """Unpin whatever else is pinned on the page: one pin per article (12.11)."""
    Comment.objects.filter(page=page, is_pinned=True).exclude(pk=keep).update(
        is_pinned=False
    )


@transaction.atomic
def pin(*, comment, actor) -> Comment:
    """One pinned comment per article (design 5.6)."""
    if not can_moderate(actor):
        raise CommentError("需要内容编辑权限")
    problem = pin_problem(comment)
    if problem:
        raise CommentError(problem)
    release_pin(comment.page, keep=comment.pk)
    comment.is_pinned = True
    comment.save(update_fields=["is_pinned"])
    transaction.on_commit(lambda: refresh_page(comment.page))
    return comment


@transaction.atomic
def unpin(*, comment, actor) -> Comment:
    if not can_moderate(actor):
        raise CommentError("需要内容编辑权限")
    comment.is_pinned = False
    comment.save(update_fields=["is_pinned"])
    transaction.on_commit(lambda: refresh_page(comment.page))
    return comment


def _own(comment, actor) -> None:
    if not getattr(actor, "is_authenticated", False) or comment.author_id != actor.pk:
        raise CommentError("只能改自己的评论")


@transaction.atomic
def edit(*, comment, actor, body) -> Comment:
    """The author rewrites the body; it is reviewed again (design 5.6)."""
    _own(comment, actor)
    if not comment.visible:
        raise CommentError("这条评论已经不能编辑了")
    body = (body or "").strip()
    if not body:
        raise CommentError("评论不能为空")
    if len(body) > MAX_BODY:
        raise CommentError(f"评论最多 {MAX_BODY} 字")
    if body == comment.body:
        return comment
    comment.body = body
    comment.edited_at = timezone.now()
    comment.save(update_fields=["body", "edited_at"])
    transaction.on_commit(lambda: _after_write(comment))
    return comment


@transaction.atomic
def delete(*, comment, actor) -> Comment:
    """The author deletes: body cleared, row kept so replies stay threaded."""
    _own(comment, actor)
    if comment.is_deleted:
        return comment
    comment.is_deleted = True
    comment.is_pinned = False
    comment.body = ""
    comment.save(update_fields=["is_deleted", "is_pinned", "body"])
    transaction.on_commit(lambda: refresh_page(comment.page))
    return comment


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
