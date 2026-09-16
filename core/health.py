"""Health checks for /healthz (design 16.6)."""

from __future__ import annotations

import shutil
from datetime import datetime, timedelta
from pathlib import Path

from django.conf import settings
from django.core.cache import cache
from django.db import connection, transaction
from django.db.models import Q
from django.utils import timezone
from django.utils.dateparse import parse_datetime

from core.models import HealthProbe

HEALTH_PROBE_BUSY_TIMEOUT_MS = 200
BUSY_DETAIL = "busy: another write in progress"
_BUSY_MARKERS = ("database is locked", "database is busy")

WORKER_HEARTBEAT_CACHE_KEY = "sjtu_ow:worker_heartbeat"
WORKER_HEARTBEAT_INTERVAL_SECONDS = 30
WORKER_HEARTBEAT_STALE_SECONDS = 120
TASK_BACKLOG_STALE_SECONDS = 600


class _ProbeRollback(Exception):
    """Sentinel used to roll back the health-check write."""


def _is_sqlite_busy(exc: BaseException) -> bool:
    current: BaseException | None = exc
    seen: set[int] = set()
    while current is not None and id(current) not in seen:
        seen.add(id(current))
        message = str(current).lower()
        if any(marker in message for marker in _BUSY_MARKERS):
            return True
        current = current.__cause__ or current.__context__
    return False


def _busy_timeout_ms() -> int:
    return int(
        getattr(settings, "HEALTH_PROBE_BUSY_TIMEOUT_MS", HEALTH_PROBE_BUSY_TIMEOUT_MS)
    )


def _default_busy_timeout_ms() -> int:
    timeout_s = connection.settings_dict.get("OPTIONS", {}).get("timeout", 5)
    return int(float(timeout_s) * 1000)


def _pragma_busy_timeout(ms: int) -> None:
    with connection.cursor() as cursor:
        cursor.execute(f"PRAGMA busy_timeout={int(ms)}")


def check_database() -> tuple[bool, str]:
    """Verify the default database can read and write the probe table."""
    previous_ms = None
    try:
        connection.ensure_connection()
        with connection.cursor() as cursor:
            cursor.execute("PRAGMA busy_timeout")
            row = cursor.fetchone()
            previous_ms = int(row[0]) if row else _default_busy_timeout_ms()
        _pragma_busy_timeout(_busy_timeout_ms())
        with connection.cursor() as cursor:
            cursor.execute("SELECT 1")
            if cursor.fetchone() is None:
                return False, "database read failed"
        with transaction.atomic():
            HealthProbe.objects.create(token="__healthz__")
            if not HealthProbe.objects.filter(token="__healthz__").exists():
                raise RuntimeError("database write did not persist")
            raise _ProbeRollback
    except _ProbeRollback:
        return True, "ok"
    except Exception as exc:  # noqa: BLE001 — health endpoint must not raise
        if _is_sqlite_busy(exc):
            return True, BUSY_DETAIL
        return False, str(exc)
    finally:
        try:
            restore_ms = (
                previous_ms if previous_ms is not None else _default_busy_timeout_ms()
            )
            _pragma_busy_timeout(restore_ms)
        except Exception:  # noqa: BLE001 — never fail the probe while restoring
            pass


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


def _parse_heartbeat(raw: object) -> datetime | None:
    if isinstance(raw, datetime):
        stamp = raw
    elif isinstance(raw, str):
        stamp = parse_datetime(raw)
        if stamp is None:
            try:
                stamp = datetime.fromisoformat(raw)
            except ValueError:
                return None
    else:
        return None
    if timezone.is_naive(stamp):
        stamp = timezone.make_aware(stamp, timezone.get_current_timezone())
    return stamp


def check_worker_heartbeat() -> tuple[bool, str]:
    """Fail when the worker has not written a heartbeat in two minutes."""
    raw = cache.get(WORKER_HEARTBEAT_CACHE_KEY)
    if not raw:
        return False, "心跳缺失"
    stamp = _parse_heartbeat(raw)
    if stamp is None:
        return False, "心跳无效"
    age = (timezone.now() - stamp).total_seconds()
    if age > WORKER_HEARTBEAT_STALE_SECONDS:
        return False, f"心跳过期（{int(age)} 秒未更新）"
    return True, f"ok ({int(age)}s ago)"


def check_task_backlog() -> tuple[bool, str]:
    """Fail when a READY task has been waiting more than 10 minutes."""
    from django_tasks.base import TaskResultStatus
    from django_tasks_db.models import DBTaskResult, get_date_max

    now = timezone.now()
    cutoff = now - timedelta(seconds=TASK_BACKLOG_STALE_SECONDS)
    date_max = get_date_max()
    waiting = DBTaskResult.objects.filter(
        status=TaskResultStatus.READY,
        enqueued_at__lte=cutoff,
    ).filter(Q(run_after=date_max) | Q(run_after__lte=now))
    count = waiting.count()
    if count:
        return False, f"{count} 个任务等待超过 10 分钟"
    return True, "ok"


def run_health_checks() -> dict:
    """Run checks that affect the HTTP status (database, disk, worker, backlog)."""
    database_ok, database_detail = check_database()
    disk_ok, disk_detail = check_disk()
    heartbeat_ok, heartbeat_detail = check_worker_heartbeat()
    backlog_ok, backlog_detail = check_task_backlog()
    blocking_ok = database_ok and disk_ok and heartbeat_ok and backlog_ok
    return {
        "status": "ok" if blocking_ok else "error",
        "ok": blocking_ok,
        "checks": {
            "database": {"ok": database_ok, "detail": database_detail},
            "disk": {"ok": disk_ok, "detail": disk_detail},
            "worker_heartbeat": {
                "ok": heartbeat_ok,
                "detail": heartbeat_detail,
                "affects_status": True,
            },
            "task_backlog": {
                "ok": backlog_ok,
                "detail": backlog_detail,
                "affects_status": True,
            },
        },
    }
