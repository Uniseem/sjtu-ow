"""Background tasks: mail delivery, font processing and prerendering."""

from __future__ import annotations

import logging
from datetime import timedelta

from django.utils import timezone
from django_tasks import task

from core.mail import deliver_email_payload

logger = logging.getLogger(__name__)

# Initial send, then three retries (design 10.1 / appendix C).
MAIL_RETRY_DELAYS = (60, 300, 1800)
# Saved inside a reminder's window, the reminder still waits this long, so
# the admin's edits are done before anyone is mailed (design 13.17, v7.10).
REMINDER_GRACE = timedelta(minutes=10)


def reminder_due(run_at, starts_at):
    """When to send a reminder arranged now: its own time, but no sooner than
    ``REMINDER_GRACE`` from now, unless that is already past the start (then
    at once, as before; a late reminder is better than none)."""
    now = timezone.now()
    due = max(run_at, now + REMINDER_GRACE)
    return due if due < starts_at else max(run_at, now)


def enqueue_once(task_obj, *args, run_after=None, earlier_counts=False):
    """Enqueue unless the same task with the same arguments already waits
    (design 13.17, v7.10): autosave saves a tournament or scrim many times
    a minute, and each save used to arrange its reminders again.

    ``earlier_counts``: a waiting one due no later than ``run_after`` will
    do, because the task re-reads its object and reschedules itself when
    it comes too early (the reminders, the scrim's auto-finish). Otherwise
    only one due at the same moment counts (a page refresh runs once).
    Returns the new result, or None when one was already waiting."""
    from django_tasks_db.models import DBTaskResult, get_date_max

    wanted = {"args": list(args), "kwargs": {}}
    waiting = DBTaskResult.objects.filter(
        status="READY", task_path=task_obj.module_path
    ).values_list("args_kwargs", "run_after")
    soonest = get_date_max()
    for args_kwargs, due in waiting:
        if args_kwargs != wanted:
            continue
        # No run_after is stored as the far future and means "as soon as possible".
        at_once = due == soonest
        if run_after is None:
            if at_once:
                return None
            continue
        if due == run_after:
            return None
        if earlier_counts and (at_once or due <= run_after):
            return None
    if run_after is None:
        return task_obj.enqueue(*args)
    return task_obj.using(run_after=run_after).enqueue(*args)


@task
def deliver_queued_email(payload: dict, attempt: int = 0) -> None:
    """Deliver one queued email; reschedule on failure with 1m / 5m / 30m delays."""
    try:
        deliver_email_payload(payload)
    except Exception:
        if attempt < len(MAIL_RETRY_DELAYS):
            run_after = timezone.now() + timedelta(seconds=MAIL_RETRY_DELAYS[attempt])
            deliver_queued_email.using(run_after=run_after).enqueue(
                payload, attempt + 1
            )
        raise


# Font slicing runs one at a time; a waiting task retries for about an hour.
FONT_REQUEUE_LIMIT = 120


@task
def process_font_face(face_id: int, attempt: int = 0) -> None:
    """Slice one font weight (design 13.12.2). Waits if another font is running."""
    from core.fonts.services import REQUEUE_DELAY_SECONDS, run_face_processing

    result = run_face_processing(face_id)
    if result == "requeue" and attempt < FONT_REQUEUE_LIMIT:
        run_after = timezone.now() + timedelta(seconds=REQUEUE_DELAY_SECONDS)
        process_font_face.using(run_after=run_after).enqueue(face_id, attempt + 1)


@task
def delete_retired_font_slices(paths: list) -> None:
    """Delete slice files replaced a day ago (design 13.12.2)."""
    from core.fonts.services import delete_unreferenced_slices

    delete_unreferenced_slices(paths)


@task
def prerender_page(path: str) -> None:
    """Generate one static page (design 13.13.4)."""
    from core import prerender

    if not prerender.is_enabled():
        return
    prerender.generate(path)


@task
def prerender_all() -> None:
    """Rebuild every static page: nightly fallback and after an upgrade."""
    from core import prerender

    if not prerender.is_enabled():
        return
    stats = prerender.generate_all()
    logger.info("预渲染全量完成：%s", stats)


@task
def remove_prerendered(path: str) -> None:
    """Delete one page's static files (design 13.13.5)."""
    from core import prerender

    if not prerender.is_enabled():
        return
    prerender.drop(path)


@task
def send_broadcast(broadcast_id: int) -> None:
    """「通知全体成员」 (design 10.4): each letter is queued on its own, so
    the SMTP retries of 10.1 apply per person."""
    from core.models import Broadcast
    from core.services import deliver

    broadcast = Broadcast.objects.filter(pk=broadcast_id).first()
    if broadcast is not None:
        deliver(broadcast)
