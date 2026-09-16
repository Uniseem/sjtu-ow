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
