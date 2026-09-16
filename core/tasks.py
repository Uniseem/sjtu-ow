"""Background tasks for mail delivery."""

from __future__ import annotations

from datetime import timedelta

from django.utils import timezone
from django_tasks import task

from core.mail import deliver_email_payload

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
