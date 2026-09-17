import json
import sqlite3
import time
from types import SimpleNamespace

import pytest
from django.db import connection
from django.db.backends.utils import CursorWrapper
from django.db.utils import OperationalError
from django.urls import reverse


@pytest.mark.django_db
def test_healthz_returns_200(client, worker_heartbeat):
    response = client.get(reverse("healthz"))
    # A bare 503 says nothing about which check failed (round 044, first CI run).
    assert response.status_code == 200, response.content.decode()
    payload = json.loads(response.content)
    assert payload["status"] == "ok"
    assert payload["checks"]["database"]["ok"] is True
    assert payload["checks"]["database"]["detail"] == "ok"
    assert payload["checks"]["disk"]["ok"] is True


@pytest.mark.django_db(transaction=True)
def test_healthz_returns_200_when_database_is_busy(client, worker_heartbeat):
    connection.close()
    db_path = str(connection.settings_dict["NAME"])
    blocker = sqlite3.connect(db_path, timeout=30)
    blocker.isolation_level = None
    blocker.execute("BEGIN IMMEDIATE")
    try:
        started = time.monotonic()
        response = client.get(reverse("healthz"))
        elapsed = time.monotonic() - started
    finally:
        blocker.execute("ROLLBACK")
        blocker.close()

    assert elapsed < 1.0
    assert response.status_code == 200, response.content.decode()
    payload = json.loads(response.content)
    assert payload["status"] == "ok"
    assert payload["checks"]["database"]["ok"] is True
    assert payload["checks"]["database"]["detail"] == (
        "busy: another write in progress"
    )


@pytest.mark.django_db(transaction=True)
def test_healthz_returns_503_when_database_not_writable(client, monkeypatch):
    original = CursorWrapper.execute

    def execute(self, sql, params=None):
        stripped = sql.lstrip().upper()
        writes = ("INSERT", "UPDATE", "DELETE", "CREATE", "DROP", "ALTER")
        if stripped.startswith(writes):
            raise OperationalError("attempt to write a readonly database")
        if params is None:
            return original(self, sql)
        return original(self, sql, params)

    monkeypatch.setattr(CursorWrapper, "execute", execute)
    response = client.get(reverse("healthz"))
    assert response.status_code == 503
    payload = json.loads(response.content)
    assert payload["status"] == "error"
    assert payload["checks"]["database"]["ok"] is False


@pytest.mark.django_db
def test_healthz_returns_503_when_heartbeat_expired(client):
    from datetime import timedelta

    from django.core.cache import cache
    from django.utils import timezone

    from core.health import WORKER_HEARTBEAT_CACHE_KEY

    cache.set(
        WORKER_HEARTBEAT_CACHE_KEY,
        (timezone.now() - timedelta(minutes=3)).isoformat(),
        timeout=600,
    )
    response = client.get(reverse("healthz"))
    assert response.status_code == 503
    payload = json.loads(response.content)
    assert payload["checks"]["worker_heartbeat"]["ok"] is False
    assert "心跳过期" in payload["checks"]["worker_heartbeat"]["detail"]


@pytest.mark.django_db
def test_healthz_returns_503_when_task_backlog(client, worker_heartbeat):
    from datetime import timedelta

    from django.utils import timezone
    from django_tasks.base import TaskResultStatus
    from django_tasks_db.models import DBTaskResult, get_date_max

    row = DBTaskResult.objects.create(
        args_kwargs={"args": [], "kwargs": {}},
        task_path="core.tasks.deliver_queued_email",
        backend_name="default",
        queue_name="default",
        run_after=get_date_max(),
        status=TaskResultStatus.READY,
    )
    DBTaskResult.objects.filter(pk=row.pk).update(
        enqueued_at=timezone.now() - timedelta(minutes=11)
    )
    response = client.get(reverse("healthz"))
    assert response.status_code == 503
    payload = json.loads(response.content)
    assert payload["checks"]["task_backlog"]["ok"] is False


def _disk_with_free_percent(monkeypatch, percent):
    from core import health

    usage = SimpleNamespace(total=100, used=100 - percent, free=percent)
    monkeypatch.setattr(health.shutil, "disk_usage", lambda _path: usage)


@pytest.mark.parametrize(
    "percent, healthy",
    [(21, True), (20, False), (19, False)],
)
def test_disk_check_needs_more_than_twenty_percent_free(
    monkeypatch, tmp_path, percent, healthy
):
    """Design 16.6: free space must be *more than* 20%, so exactly 20% fails.

    The healthz tests above only ever saw the disk of whatever machine ran
    them, so the threshold itself had no test.
    """
    from core import health

    _disk_with_free_percent(monkeypatch, percent)
    ok, detail = health.check_disk(tmp_path)
    assert ok is healthy, detail


@pytest.mark.django_db
def test_healthz_returns_503_when_disk_is_nearly_full(
    client, worker_heartbeat, monkeypatch
):
    _disk_with_free_percent(monkeypatch, 10)
    response = client.get(reverse("healthz"))
    assert response.status_code == 503
    payload = json.loads(response.content)
    assert payload["checks"]["disk"]["ok"] is False


@pytest.mark.django_db
def test_home_returns_200(client):
    response = client.get(reverse("home"))
    assert response.status_code == 200
    assert "上海交通大学守望先锋社区" in response.content.decode("utf-8")
