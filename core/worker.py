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


def write_worker_heartbeat() -> None:
    cache.set(
        WORKER_HEARTBEAT_CACHE_KEY,
        timezone.now().isoformat(),
        timeout=WORKER_HEARTBEAT_STALE_SECONDS * 2,
    )


def _heartbeat_loop() -> None:
    while not _stop.is_set():
        try:
            write_worker_heartbeat()
        except Exception:
            logger.exception("Failed to write worker heartbeat")
        finally:
            close_old_connections()
        _stop.wait(WORKER_HEARTBEAT_INTERVAL_SECONDS)


def start_heartbeat_thread() -> None:
    """Start a daemon thread that writes the shared cache key every 30 seconds."""
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
