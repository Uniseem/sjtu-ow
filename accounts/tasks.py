"""Worker tasks for accounts (design-details 2.3, v6.11)."""

from __future__ import annotations

from django.core.cache import cache
from django_tasks import task


@task
def notify_avatars_waiting() -> None:
    """The reminder avatars_waiting_soon asked for: one email listing every
    face still waiting. The next upload may ask for a new one."""
    from accounts.notifications import WAITING_KEY, send_avatars_waiting

    cache.delete(WAITING_KEY)
    send_avatars_waiting()
