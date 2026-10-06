"""Round 214, C2: a worker killed mid-task must not strand it RUNNING forever
(design 16.2, v7.17)."""

from unittest import mock

import pytest
from django.core.management import call_command
from django_tasks.base import TaskResultStatus
from django_tasks_db.models import DBTaskResult

from core.tasks import prerender_page
from core.worker import reset_orphaned_running_tasks


@pytest.mark.django_db
def test_orphaned_running_tasks_go_back_to_ready():
    row = DBTaskResult.objects.get(id=prerender_page.enqueue("/").id)
    done = DBTaskResult.objects.get(id=prerender_page.enqueue("/done/").id)
    done.status = TaskResultStatus.SUCCESSFUL
    done.save(update_fields=["status"])

    row.claim("worker-dead")  # RUNNING, started_at set — then the worker died
    assert DBTaskResult.objects.running().count() == 1

    assert reset_orphaned_running_tasks() == 1
    row.refresh_from_db()
    assert row.status == TaskResultStatus.READY
    assert row.started_at is None
    done.refresh_from_db()
    assert done.status == TaskResultStatus.SUCCESSFUL  # finished rows untouched

    assert reset_orphaned_running_tasks() == 0  # nothing left to reset


@pytest.mark.django_db
def test_run_worker_resets_before_taking_work():
    row = DBTaskResult.objects.get(id=prerender_page.enqueue("/").id)
    row.claim("worker-dead")
    with (
        mock.patch(
            "core.management.commands.run_worker.start_heartbeat_thread"
        ) as heartbeat,
        mock.patch(
            "django_tasks_db.management.commands.db_worker.Command.handle"
        ) as take_work,
    ):
        call_command("run_worker")
    heartbeat.assert_called_once_with()
    take_work.assert_called_once()
    row.refresh_from_db()
    assert row.status == TaskResultStatus.READY
