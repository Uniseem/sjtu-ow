"""Design 11.11 (docs page) and 16.5 (daily cleanup)."""

from datetime import timedelta
from io import StringIO

import pytest
from django.core.management import call_command
from django.utils import timezone

from accounts.models import User
from integrations import services as api_services
from integrations.models import (
    ApiRequestLog,
    DeliveryStatus,
    WebhookDelivery,
)


def make_user(email, *, superuser=False, staff=False):
    now = timezone.now()
    if superuser:
        return User.objects.create_superuser(
            email=email, password="Correct-Horse-Battery-1", nickname="超管"
        )
    return User.objects.create_user(
        email=email,
        password="Correct-Horse-Battery-1",
        nickname="普通人",
        is_staff=staff,
        agreed_terms_at=now,
        agreed_cross_border_at=now,
    )


# --- docs page -----------------------------------------------------------------


@pytest.mark.django_db
def test_docs_page_is_closed_to_anonymous_visitors(client):
    for path in ("/api/v1/docs/", "/api/v1/schema/"):
        response = client.get(path)
        assert response.status_code in (401, 403), path
        assert b"tournaments" not in response.content, path


@pytest.mark.django_db
def test_docs_page_is_closed_to_a_normal_staff_member(client):
    make_user("staff@example.com", staff=True)
    client.login(email="staff@example.com", password="Correct-Horse-Battery-1")
    response = client.get("/api/v1/docs/")
    assert response.status_code == 403
    assert b"tournaments" not in response.content


@pytest.mark.django_db
def test_docs_page_opens_for_a_superuser(client):
    make_user("root@example.com", superuser=True)
    client.login(email="root@example.com", password="Correct-Horse-Battery-1")

    docs = client.get("/api/v1/docs/")
    assert docs.status_code == 200
    html = docs.content.decode()
    # The page must render from our own static files. A CDN build is blocked by
    # the site's CSP and renders blank, and the project does not use CDNs.
    for host in ("cdn.jsdelivr.net", "unpkg.com", "cdnjs.cloudflare.com"):
        assert host not in html, host
    assert "/static/drf_spectacular_sidecar/" in html

    schema = client.get("/api/v1/schema/")
    assert schema.status_code == 200
    body = schema.content.decode()
    assert "/api/v1/tournaments" in body
    # Design 11.11: only the public API, never Wagtail's admin API.
    assert "/admin/api" not in body


# --- cleanup -------------------------------------------------------------------


def make_log(days_old):
    log = ApiRequestLog.objects.create(
        request_id="x", method="GET", path="/api/v1/ping", status_code=200
    )
    ApiRequestLog.objects.filter(pk=log.pk).update(
        created_at=timezone.now() - timedelta(days=days_old)
    )
    return log


def make_delivery(client, days_old, status=DeliveryStatus.SUCCEEDED):
    delivery = WebhookDelivery.objects.create(
        client=client, event_type="ping", payload={}, status=status
    )
    WebhookDelivery.objects.filter(pk=delivery.pk).update(
        created_at=timezone.now() - timedelta(days=days_old)
    )
    return delivery


@pytest.fixture
def api_client(db):
    client, _ = api_services.create_client(
        name="上游", scopes=["tournaments:read"], allowed_includes=[]
    )
    return client


@pytest.mark.django_db
def test_docs_page_relaxes_csp_only_for_itself(client):
    """Swagger UI needs inline script/style; nothing else on the site does."""
    make_user("root2@example.com", superuser=True)
    client.login(email="root2@example.com", password="Correct-Horse-Battery-1")

    docs = client.get("/api/v1/docs/")
    policy = docs.headers.get("Content-Security-Policy", "")
    assert "'unsafe-inline'" in policy
    assert "'unsafe-eval'" not in policy
    assert "http" not in policy  # no external origin is allowed

    home = client.get("/")
    assert "'unsafe-inline'" not in home.headers.get("Content-Security-Policy", "")


@pytest.mark.django_db
def test_cleanup_respects_each_retention_window(api_client):
    fresh_log = make_log(10)
    old_log = make_log(100)
    fresh_delivery = make_delivery(api_client, 30)
    old_delivery = make_delivery(api_client, 200)

    out = StringIO()
    call_command("cleanup_old_data", stdout=out)

    assert ApiRequestLog.objects.filter(pk=fresh_log.pk).exists()
    assert not ApiRequestLog.objects.filter(pk=old_log.pk).exists()
    assert WebhookDelivery.objects.filter(pk=fresh_delivery.pk).exists()
    assert not WebhookDelivery.objects.filter(pk=old_delivery.pk).exists()
    assert "已删除" in out.getvalue()


@pytest.mark.django_db
def test_cleanup_keeps_a_pending_delivery_however_old(api_client):
    """A retry still waiting must not be deleted out from under the worker."""
    stuck = make_delivery(api_client, 300, status=DeliveryStatus.PENDING)

    call_command("cleanup_old_data", stdout=StringIO())

    assert WebhookDelivery.objects.filter(pk=stuck.pk).exists()


@pytest.mark.django_db
def test_dry_run_deletes_nothing(api_client):
    old_log = make_log(100)
    old_delivery = make_delivery(api_client, 200)

    out = StringIO()
    call_command("cleanup_old_data", "--dry-run", stdout=out)

    assert ApiRequestLog.objects.filter(pk=old_log.pk).exists()
    assert WebhookDelivery.objects.filter(pk=old_delivery.pk).exists()
    assert "将删除" in out.getvalue()


@pytest.mark.django_db
def test_cleanup_removes_expired_sessions():
    from django.contrib.sessions.models import Session

    Session.objects.create(
        session_key="expired-key",
        session_data="x",
        expire_date=timezone.now() - timedelta(days=1),
    )
    Session.objects.create(
        session_key="live-key",
        session_data="x",
        expire_date=timezone.now() + timedelta(days=1),
    )

    call_command("cleanup_old_data", stdout=StringIO())

    assert not Session.objects.filter(session_key="expired-key").exists()
    assert Session.objects.filter(session_key="live-key").exists()
