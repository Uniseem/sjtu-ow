"""Drafts that save themselves (design 13.17, v7.9).

Articles, plain pages, the homepage's pins and the news section's intro save
as you type, as drafts: what a page shows changes only when someone presses
「发布」. ``save_draft`` keeps one revision per stretch of one person's
editing (Wagtail's ``overwrite_revision``) instead of one per autosave;
``start_article`` makes a new article exist from its first change, title and
category still empty if so (publishing checks them, as it always did).
"""

from __future__ import annotations

from datetime import timedelta

from django.utils import timezone

OVERWRITE_WITHIN = timedelta(minutes=30)
# The page row needs a title to be saved at all; the draft keeps it empty and
# the lists say 「（无标题）」. Publishing replaces it with the real one.
UNTITLED = "（无标题）"

# 212, D3: two people with the same editor open would overwrite each other's
# saves, so the form says which revision it started from.
STALE_MESSAGE = (
    "另一个人在你打开以后改过这篇，你的改动没有存；刷新页面看一看现在的内容，再重新改。"
)


def stale_base(page, request) -> bool:
    """The page changed since this editor opened it: the form posts the
    revision it started from (a hidden ``latest_revision``), and a mismatch
    means saving would overwrite someone else's work. Forms without the
    field (an older page still open, a new article before it exists) save as
    before; a value that is not a number is refused rather than ignored."""
    posted = (request.POST.get("latest_revision") or "").strip()
    if not posted:
        return False
    try:
        base = int(posted)
    except ValueError:
        return True
    return page.latest_revision_id != base


def overwritable(page, user):
    """The revision this person may write over: their own latest draft,
    neither live nor scheduled, touched in the last half hour."""
    latest = page.latest_revision
    if latest is None or user is None or latest.user_id != user.pk:
        return None
    if latest.pk == page.live_revision_id or latest.approved_go_live_at is not None:
        return None
    if latest.created_at < timezone.now() - OVERWRITE_WITHIN:
        return None
    return latest


def save_draft(page, draft, user):
    """``draft`` (the page as its latest revision has it, with the changes
    applied) becomes the newest draft. One log entry per stretch, too."""
    from core.autosave import log_edit

    revision = draft.save_revision(
        user=user, clean=False, overwrite_revision=overwritable(page, user)
    )
    log_edit(page, user)
    return revision


def start_article(parent, page, user):
    """A new article from its first change: created as a draft under
    ``parent``, whatever is still empty."""
    from wagtail.log_actions import log

    title = page.title
    page.title = title or UNTITLED
    page.live = False
    parent.add_child(instance=page)
    page.title = title
    revision = page.save_revision(user=user, clean=False)
    log(
        instance=page,
        action="wagtail.create",
        user=user,
        revision=revision,
        content_changed=True,
        title=title or UNTITLED,  # a log entry needs a label
    )
    return page
