"""Round 135: a scrim finishes six hours after it starts (design 9.1, v6.30)."""

from datetime import timedelta
from unittest import mock

import pytest
from django.utils import timezone

from scrims import services
from scrims.models import Scrim, ScrimStatus
from scrims.tasks import finish_past_scrim
from scrims.tests.test_scrims import make_scrim


def _arranged(django_capture_on_commit_callbacks, action):
    with mock.patch("scrims.tasks.finish_past_scrim") as task:
        with django_capture_on_commit_callbacks(execute=True):
            action()
    return task


@pytest.mark.django_db
def test_publishing_and_saving_arrange_it(django_capture_on_commit_callbacks):
    scrim = make_scrim(status=ScrimStatus.DRAFT)
    task = _arranged(
        django_capture_on_commit_callbacks, lambda: services.publish(scrim=scrim)
    )
    task.using.assert_called_once_with(run_after=scrim.starts_at + timedelta(hours=6))
    task.using.return_value.enqueue.assert_called_once_with(scrim.pk)

    scrim.starts_at += timedelta(days=1)
    scrim.save()
    task = _arranged(
        django_capture_on_commit_callbacks, lambda: services.after_change(scrim)
    )
    task.using.assert_called_once_with(run_after=scrim.starts_at + timedelta(hours=6))


@pytest.mark.django_db
def test_a_draft_edit_arranges_nothing(django_capture_on_commit_callbacks):
    scrim = make_scrim(status=ScrimStatus.DRAFT)
    task = _arranged(
        django_capture_on_commit_callbacks, lambda: services.after_change(scrim)
    )
    task.using.assert_not_called()


@pytest.mark.django_db
def test_six_hours_after_the_start_it_is_finished():
    scrim = make_scrim(starts_at=timezone.now() - timedelta(hours=7))
    assert finish_past_scrim.func(scrim.pk) == "finished"
    scrim.refresh_from_db()
    assert scrim.status == ScrimStatus.FINISHED
    assert scrim in services.public_scrims()
    assert finish_past_scrim.func(scrim.pk) == "not_published"


@pytest.mark.django_db
def test_too_early_or_cancelled_leaves_it_alone():
    scrim = make_scrim(starts_at=timezone.now() - timedelta(hours=2))
    with mock.patch("scrims.tasks.finish_past_scrim") as task:
        assert finish_past_scrim.func(scrim.pk) == "rescheduled"
    task.using.assert_called_once_with(run_after=scrim.starts_at + timedelta(hours=6))
    scrim.refresh_from_db()
    assert scrim.status == ScrimStatus.PUBLISHED

    Scrim.objects.filter(pk=scrim.pk).update(
        status=ScrimStatus.CANCELLED, starts_at=timezone.now() - timedelta(days=1)
    )
    assert finish_past_scrim.func(scrim.pk) == "not_published"
    scrim.refresh_from_db()
    assert scrim.status == ScrimStatus.CANCELLED
