"""Health checks for /healthz (design 16.6)."""

from __future__ import annotations

import shutil
from pathlib import Path

from django.conf import settings
from django.db import connection, transaction


class _ProbeRollback(Exception):
    """Sentinel used to roll back the health-check write."""


def check_database() -> tuple[bool, str]:
    """Verify the default database can read and write a real table."""
    try:
        with transaction.atomic():
            with connection.cursor() as cursor:
                cursor.execute("SELECT 1")
                if cursor.fetchone() is None:
                    raise RuntimeError("database read failed")
                cursor.execute(
                    "DELETE FROM django_content_type "
                    "WHERE app_label = %s AND model = %s",
                    ["__healthz__", "__probe__"],
                )
                cursor.execute(
                    "INSERT INTO django_content_type (app_label, model) "
                    "VALUES (%s, %s)",
                    ["__healthz__", "__probe__"],
                )
                cursor.execute(
                    "SELECT id FROM django_content_type "
                    "WHERE app_label = %s AND model = %s",
                    ["__healthz__", "__probe__"],
                )
                if cursor.fetchone() is None:
                    raise RuntimeError("database write did not persist")
            raise _ProbeRollback
    except _ProbeRollback:
        return True, "ok"
    except Exception as exc:  # noqa: BLE001 — health endpoint must not raise
        return False, str(exc)


def check_disk(path: Path | None = None) -> tuple[bool, str]:
    """Fail when free space on the database volume is at most 20%."""
    target = path or Path(settings.DATABASE_PATH).parent
    target.mkdir(parents=True, exist_ok=True)
    usage = shutil.disk_usage(target)
    free_ratio = usage.free / usage.total if usage.total else 0
    minimum = getattr(settings, "DISK_MIN_FREE_RATIO", 0.20)
    if free_ratio <= minimum:
        return False, f"free space {free_ratio:.1%} is at or below {minimum:.0%}"
    return True, f"free space {free_ratio:.1%}"


def check_worker_heartbeat() -> tuple[bool, str]:
    """Worker liveness.

    M1 will have the worker write a cache key every 30 seconds. This check
    will then fail the overall /healthz response if the key is older than
    2 minutes. Not included in the 200/503 decision in M0.
    """
    return True, "skipped_until_m1"


def check_task_backlog() -> tuple[bool, str]:
    """Queued-task backlog.

    M1 will fail /healthz when any task has been waiting more than 10 minutes.
    Not included in the 200/503 decision in M0.
    """
    return True, "skipped_until_m1"


def run_health_checks() -> dict:
    """Run M0 checks that affect the HTTP status, plus M1 placeholders."""
    database_ok, database_detail = check_database()
    disk_ok, disk_detail = check_disk()
    heartbeat_ok, heartbeat_detail = check_worker_heartbeat()
    backlog_ok, backlog_detail = check_task_backlog()
    blocking_ok = database_ok and disk_ok
    return {
        "status": "ok" if blocking_ok else "error",
        "ok": blocking_ok,
        "checks": {
            "database": {"ok": database_ok, "detail": database_detail},
            "disk": {"ok": disk_ok, "detail": disk_detail},
            "worker_heartbeat": {
                "ok": heartbeat_ok,
                "detail": heartbeat_detail,
                "affects_status": False,
            },
            "task_backlog": {
                "ok": backlog_ok,
                "detail": backlog_detail,
                "affects_status": False,
            },
        },
    }
