"""Worker tasks for tournaments (design 8.1, v6.24)."""

from __future__ import annotations

from django.utils import timezone
from django_tasks import task

from tournaments.models import Tournament, TournamentStatus


@task
def send_tournament_reminder(tournament_id: int) -> str:
    """Remind every player on an approved roster. Safe to schedule more than
    once: the tournament is re-read here, so a task left over from an earlier
    start time reschedules itself or does nothing."""
    from tournaments import notifications, services

    tournament = Tournament.objects.filter(pk=tournament_id).first()
    if tournament is None:
        return "gone"
    if tournament.status != TournamentStatus.PUBLISHED:
        return "not_published"
    if tournament.starts_at is None:
        return "no_start"
    if tournament.reminder_sent_at is not None:
        return "already_sent"

    now = timezone.now()
    if now >= tournament.starts_at:
        return "too_late"
    due = services.reminder_time(tournament)
    if now < due:
        # The start moved later; come back when it is actually due.
        send_tournament_reminder.using(run_after=due).enqueue(tournament_id)
        return "rescheduled"

    sent = notifications.tournament_reminder(tournament)
    # With nobody approved yet it stays unsent, so saving the tournament
    # later arranges it again. The pool hears only once teams are being
    # formed (v6.29): before that the admin has most likely not started.
    if not sent:
        return "sent:0"
    pool = notifications.unplaced_reminder(tournament)
    Tournament.objects.filter(pk=tournament_id, reminder_sent_at__isnull=True).update(
        reminder_sent_at=now
    )
    return f"sent:{sent}" + (f",pool:{pool}" if pool else "")
