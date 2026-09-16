from datetime import timedelta

import pytest
from django.core import mail
from django.core.mail import send_mail
from django.utils import timezone
from django_tasks.base import TaskResultStatus
from django_tasks_db.models import DBTaskResult, get_date_max

from core.crypto import decrypt_value, encrypt_value
from core.mail import SMTPNotConfigured, apply_subject_prefix, send_test_email
from core.models import SiteSettings
from core.tasks import MAIL_RETRY_DELAYS, deliver_queued_email


@pytest.mark.django_db
def test_smtp_password_stored_encrypted(db):
    cipher = encrypt_value("s3cret-pass")
    settings_obj = SiteSettings.objects.create(
        smtp_host="smtp.example.com",
        smtp_password=cipher,
    )
    stored = (
        SiteSettings.objects.filter(pk=settings_obj.pk)
        .values_list("smtp_password", flat=True)
        .get()
    )
    assert stored != "s3cret-pass"
    assert stored == cipher
    assert decrypt_value(stored) == "s3cret-pass"


@pytest.mark.django_db(transaction=True)
def test_send_mail_enqueues_instead_of_sending(settings):
    # Django's test environment forces locmem; restore the app queue backend.
    settings.EMAIL_BACKEND = "core.mail.QueuedEmailBackend"
    settings.EMAIL_DELIVERY_BACKEND = "django.core.mail.backends.locmem.EmailBackend"
    send_mail("Hello", "Body text", "from@example.com", ["to@example.com"])
    assert DBTaskResult.objects.count() == 1
    assert len(mail.outbox) == 0


@pytest.mark.django_db(transaction=True)
def test_worker_delivers_queued_mail(settings):
    settings.EMAIL_BACKEND = "core.mail.QueuedEmailBackend"
    settings.EMAIL_DELIVERY_BACKEND = "django.core.mail.backends.locmem.EmailBackend"
    SiteSettings.objects.create(email_subject_prefix="[SJTU OW]")
    send_mail("Hello", "Body text", "from@example.com", ["to@example.com"])
    row = DBTaskResult.objects.get()
    payload = row.args_kwargs["args"][0]
    deliver_queued_email.call(payload)
    assert len(mail.outbox) == 1
    assert apply_subject_prefix("Hello") in mail.outbox[0].subject
    html_alts = [
        content
        for content, mimetype in mail.outbox[0].alternatives
        if mimetype == "text/html"
    ]
    assert html_alts


@pytest.mark.django_db(transaction=True)
def test_failed_delivery_is_retried(settings, monkeypatch):
    settings.EMAIL_BACKEND = "core.mail.QueuedEmailBackend"
    settings.EMAIL_DELIVERY_BACKEND = "django.core.mail.backends.locmem.EmailBackend"

    def boom(payload):
        raise RuntimeError("smtp down")

    monkeypatch.setattr("core.tasks.deliver_email_payload", boom)
    send_mail("Hello", "Body text", "from@example.com", ["to@example.com"])
    payload = DBTaskResult.objects.get().args_kwargs["args"][0]
    with pytest.raises(RuntimeError, match="smtp down"):
        deliver_queued_email.call(payload, 0)
    deferred = [
        row
        for row in DBTaskResult.objects.all()
        if row.status == TaskResultStatus.READY and row.run_after != get_date_max()
    ]
    assert len(deferred) == 1
    delta = deferred[0].run_after - timezone.now()
    assert MAIL_RETRY_DELAYS[0] - 5 <= delta.total_seconds() <= MAIL_RETRY_DELAYS[0] + 5


@pytest.mark.django_db
def test_test_email_requires_smtp_config():
    SiteSettings.objects.create()
    with pytest.raises(SMTPNotConfigured):
        send_test_email("admin@example.com")


@pytest.mark.django_db
def test_task_backlog_counts_old_ready_jobs():
    from core.health import check_task_backlog

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
    ok, detail = check_task_backlog()
    assert ok is False
    assert "10 分钟" in detail
