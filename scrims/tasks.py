"""Worker tasks for scrims (design 9.1)."""

from __future__ import annotations

import logging

from django.utils import timezone
from django_tasks import task

from scrims.models import Scrim, ScrimStatus

logger = logging.getLogger(__name__)


@task
def send_scrim_reminder(scrim_id: int) -> str:
    """Remind everyone signed up. Safe to schedule more than once.

    The scrim is re-read here, so a task left over from an earlier start
    time simply reschedules itself or does nothing.
    """
    from scrims import notifications, services

    scrim = Scrim.objects.filter(pk=scrim_id).first()
    if scrim is None:
        return "gone"
    if scrim.status != ScrimStatus.PUBLISHED:
        return "not_published"
    if scrim.reminder_sent_at is not None:
        return "already_sent"

    now = timezone.now()
    if now >= scrim.starts_at:
        return "too_late"
    due = services.reminder_time(scrim)
    if now < due:
        # The start time moved later; come back when it is actually due.
        send_scrim_reminder.using(run_after=due).enqueue(scrim_id)
        return "rescheduled"

    sent = notifications.scrim_reminder(scrim)
    Scrim.objects.filter(pk=scrim_id, reminder_sent_at__isnull=True).update(
        reminder_sent_at=now
    )
    return f"sent:{sent}"
