"""Worker-process heartbeat (design 16.6)."""

from __future__ import annotations

import logging
import threading

from django.core.cache import cache
from django.db import close_old_connections
from django.utils import timezone

from core.health import (
    WORKER_HEARTBEAT_CACHE_KEY,
    WORKER_HEARTBEAT_INTERVAL_SECONDS,
    WORKER_HEARTBEAT_STALE_SECONDS,
)

logger = logging.getLogger("sjtu_ow.worker")

_thread: threading.Thread | None = None
_stop = threading.Event()


def reset_orphaned_running_tasks() -> int:
    """Put tasks still marked RUNNING back to READY. There is only ever one
    worker (design 16.2), so at startup a running task's owner is dead —
    killed mid-run by a deploy, for instance (design 16.2, v7.17, 210 复核
    C2). It runs again from the start: a half-sent broadcast may reach some
    people twice, which beats the rest never hearing it."""
    from django_tasks_db.models import DBTaskResult, TaskResultStatus

    orphaned = list(DBTaskResult.objects.running())
    for result in orphaned:
        result.status = TaskResultStatus.READY
        result.started_at = None
        result.save(update_fields=["status", "started_at"])
    if orphaned:
        logger.warning(
            "Reset %d orphaned running task(s): %s",
            len(orphaned),
            ", ".join(result.task_name for result in orphaned),
        )
    return len(orphaned)


def write_worker_heartbeat() -> None:
    cache.set(
        WORKER_HEARTBEAT_CACHE_KEY,
        timezone.now().isoformat(),
        timeout=WORKER_HEARTBEAT_STALE_SECONDS * 2,
    )


def beat() -> None:
    """One tick of the worker's beat: the heartbeat, then the jobs that ride
    on it. Each is on its own, so one failing does not stop the others."""
    from content.services import publish_due_pages
    from moderation.patrol import enqueue_if_due

    jobs = (
        (write_worker_heartbeat, "write worker heartbeat"),
        # Scheduled publishing (design 16.5, v6.50).
        (publish_due_pages, "publish scheduled pages"),
        # The AI patrol (design 5.5.3, v6.72): queued once per 30 minutes.
        (enqueue_if_due, "queue the AI patrol"),
    )
    for job, what in jobs:
        try:
            job()
        except Exception:
            logger.exception("Failed to %s", what)
        finally:
            close_old_connections()


def _heartbeat_loop() -> None:
    while not _stop.is_set():
        beat()
        _stop.wait(WORKER_HEARTBEAT_INTERVAL_SECONDS)


def start_heartbeat_thread() -> None:
    """Start a daemon thread that writes the shared cache key every 30 seconds
    and publishes pages whose scheduled time has come."""
    global _thread
    if _thread is not None and _thread.is_alive():
        return
    _stop.clear()
    write_worker_heartbeat()
    _thread = threading.Thread(
        target=_heartbeat_loop,
        name="sjtu-ow-worker-heartbeat",
        daemon=True,
    )
    _thread.start()
