"""Webhook payloads, signing and delivery (design 11.8)."""

from __future__ import annotations

import hashlib
import hmac
import json
import logging
import time
import urllib.error
import urllib.request

from django.conf import settings
from django.db import transaction
from django.utils import timezone

from core.net import UnsafeUrl, assert_public_https_url
from integrations.api import isoformat
from integrations.models import (
    ApiClient,
    DeliveryStatus,
    WebhookDelivery,
    WebhookEvent,
    WebhookPayloadMode,
)

logger = logging.getLogger(__name__)

TIMEOUT = 10  # design 11.8.3: 10 seconds
# First attempt, then these gaps. Eight tries in total (design 11.8.3).
RETRY_DELAYS = (60, 300, 1800, 7200, 21600, 43200, 86400)
MAX_ATTEMPTS = len(RETRY_DELAYS) + 1


def allow_insecure_urls() -> bool:
    return bool(getattr(settings, "WEBHOOK_ALLOW_INSECURE_URLS", False))


def validate_webhook_url(url: str) -> None:
    """Design 11.8.3: https only, never an internal address."""
    if not url:
        return
    assert_public_https_url(url, allow_insecure=allow_insecure_urls())


# --- signing -------------------------------------------------------------------


def signature(secret: str, timestamp: str, body: bytes) -> str:
    """Design 11.8.2: sha256= + HMAC(secret, timestamp + "." + raw body)."""
    digest = hmac.new(
        secret.encode(), timestamp.encode() + b"." + body, hashlib.sha256
    ).hexdigest()
    return f"sha256={digest}"


def build_headers(delivery, body: bytes, *, now=None) -> dict[str, str]:
    timestamp = str(int(now if now is not None else time.time()))
    return {
        "Content-Type": "application/json",
        "X-Webhook-Id": str(delivery.event_id),
        "X-Webhook-Event": delivery.event_type,
        "X-Webhook-Timestamp": timestamp,
        "X-Webhook-Signature": signature(
            delivery.client.webhook_secret or "", timestamp, body
        ),
    }


# --- who gets what -------------------------------------------------------------


def tournament_is_relevant(tournament, client) -> bool:
    """Design 11.8.1: upstream-reviewed tournaments, or the client's own."""
    from tournaments.models import ReviewMode

    if tournament is None:
        return False
    if tournament.source_client_id == client.pk:
        return True
    return tournament.review_mode in (ReviewMode.UPSTREAM, ReviewMode.TWO_STAGE)


def subscribers(event_type: str, *, tournament=None):
    """Every client that should receive this event, both filters applied."""
    clients = ApiClient.objects.filter(is_active=True, revoked_at__isnull=True).exclude(
        webhook_url=""
    )
    chosen = []
    for client in clients:
        if event_type not in (client.webhook_events or []):
            continue
        if tournament is not None and not tournament_is_relevant(tournament, client):
            continue
        chosen.append(client)
    return chosen


# --- payloads ------------------------------------------------------------------


def external_id_for(tournament, client):
    """Same rule as the tournament object: only its own pusher sees it."""
    if tournament is None or tournament.source_client_id != client.pk:
        return None
    return tournament.external_id or None


def registration_payload(registration, client, *, actor_type, previous_status=None):
    tournament = registration.tournament
    data = {
        "registration_id": registration.pk,
        "tournament_id": tournament.pk,
        "tournament_external_id": external_id_for(tournament, client),
        "team_id": registration.team_id,
        "status": registration.status,
        "previous_status": previous_status,
        "roster_version": registration.roster_version,
    }
    if client.webhook_payload_mode == WebhookPayloadMode.FULL:
        from integrations.serializers import registration_data

        # Design 11.8.2: everything the client may expand, except logs.
        includes = [name for name in (client.allowed_includes or []) if name != "logs"]
        data["registration"] = registration_data(
            registration, client=client, includes=includes
        )
    return data


def build_payload(event_type, *, data, actor_type, event_id, created_at=None):
    return {
        "id": str(event_id),
        "type": event_type,
        "created_at": isoformat(created_at or timezone.now()),
        "actor_type": actor_type,
        "data": data,
    }


# --- queueing ------------------------------------------------------------------


def queue_registration_event(
    registration, event_type, *, actor_type, previous_status=None
):
    """Build one delivery per subscribed client, after the transaction commits.

    The payload is frozen here, not at delivery time (design 12.10.3), so a
    retry sends exactly what the first attempt sent.
    """
    tournament = registration.tournament
    deliveries = []
    for client in subscribers(event_type, tournament=tournament):
        delivery = WebhookDelivery(
            client=client,
            event_type=event_type,
            next_attempt_at=timezone.now(),
        )
        delivery.payload = build_payload(
            event_type,
            data=registration_payload(
                registration,
                client,
                actor_type=actor_type,
                previous_status=previous_status,
            ),
            actor_type=actor_type,
            event_id=delivery.event_id,
        )
        delivery.save()
        deliveries.append(delivery)
    for delivery in deliveries:
        schedule(delivery)
    return deliveries


def queue_ping(client):
    delivery = WebhookDelivery(
        client=client,
        event_type=WebhookEvent.PING,
        next_attempt_at=timezone.now(),
    )
    delivery.payload = build_payload(
        WebhookEvent.PING,
        data={"client": client.name, "message": "这是一条测试事件。"},
        actor_type="admin",
        event_id=delivery.event_id,
    )
    delivery.save()
    schedule(delivery)
    return delivery


def schedule(delivery, *, delay=0):
    from integrations.tasks import deliver_webhook

    def enqueue():
        deliver_webhook.enqueue(delivery.pk)

    if delay:
        # The worker re-checks next_attempt_at, so a plain enqueue is enough.
        transaction.on_commit(enqueue)
    else:
        transaction.on_commit(enqueue)


# --- delivery ------------------------------------------------------------------


class _NoRedirect(urllib.request.HTTPRedirectHandler):
    """Design 11.8.3: do not follow redirects; a 3xx counts as a failure."""

    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


_opener = urllib.request.build_opener(_NoRedirect)


def post(url, body: bytes, headers: dict[str, str]):
    """Return (status_code, error). Never raises."""
    try:
        validate_webhook_url(url)
    except UnsafeUrl as exc:
        return None, f"地址不可用：{exc}"
    request = urllib.request.Request(url, data=body, headers=headers, method="POST")
    try:
        with _opener.open(request, timeout=TIMEOUT) as response:
            return response.status, ""
    except urllib.error.HTTPError as exc:
        # urllib raises for 3xx too once redirects are refused.
        return exc.code, f"HTTP {exc.code}"
    except urllib.error.URLError as exc:
        return None, f"连接失败：{exc.reason}"
    except OSError as exc:
        return None, f"连接失败：{exc}"


def attempt(delivery) -> bool:
    """One delivery attempt; records the outcome and the next retry."""
    body = json.dumps(delivery.payload, ensure_ascii=False).encode()
    headers = build_headers(delivery, body)
    status_code, error = post(delivery.client.webhook_url, body, headers)

    delivery.attempts += 1
    delivery.last_status_code = status_code
    delivery.last_error = error[:500]
    succeeded = status_code is not None and 200 <= status_code < 300
    if succeeded:
        delivery.status = DeliveryStatus.SUCCEEDED
        delivery.delivered_at = timezone.now()
        delivery.next_attempt_at = None
        delivery.last_error = ""
    elif delivery.attempts >= MAX_ATTEMPTS:
        delivery.status = DeliveryStatus.FAILED
        delivery.next_attempt_at = None
    else:
        delivery.status = DeliveryStatus.PENDING
        gap = RETRY_DELAYS[delivery.attempts - 1]
        delivery.next_attempt_at = timezone.now() + timezone.timedelta(seconds=gap)
    delivery.save(
        update_fields=[
            "attempts",
            "last_status_code",
            "last_error",
            "status",
            "delivered_at",
            "next_attempt_at",
        ]
    )
    if delivery.status == DeliveryStatus.FAILED:
        from integrations.notifications import webhook_failed

        webhook_failed(delivery)
    return succeeded


def resend(delivery):
    """Design 11.8.3: a manual resend keeps the same event id."""
    delivery.status = DeliveryStatus.PENDING
    delivery.attempts = 0
    delivery.next_attempt_at = timezone.now()
    delivery.save(update_fields=["status", "attempts", "next_attempt_at"])
    schedule(delivery)
    return delivery
