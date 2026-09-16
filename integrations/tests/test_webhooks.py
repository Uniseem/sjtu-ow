"""Design 11.8: events, subscription filters, signing, delivery and retries.

The event-flow tests run with a real transaction because the events are queued
from ``transaction.on_commit`` — without a commit there is nothing to assert.
"""

import hashlib
import hmac
import json
import time
from datetime import timedelta

import pytest
from django.core import mail
from django.test import override_settings
from django.utils import timezone

from accounts.models import ContactMethod, ContactType, GameAccount, User
from integrations import services as api_services
from integrations import webhooks
from integrations.models import (
    DeliveryStatus,
    WebhookDelivery,
    WebhookEvent,
    WebhookPayloadMode,
)
from teams import services as team_services
from tournaments import registration as reg
from tournaments.models import ReviewMode, Tournament, TournamentStatus

ALL_EVENTS = [choice[0] for choice in WebhookEvent.choices]
flow = pytest.mark.django_db(transaction=True)


def verify_webhook(headers, raw_body, webhook_secret):
    """Copied verbatim from design 11.8.2 — the receiver's own check."""
    timestamp = headers["X-Webhook-Timestamp"]
    if abs(time.time() - int(timestamp)) > 300:
        return False
    expected = (
        "sha256="
        + hmac.new(
            webhook_secret.encode(),
            timestamp.encode() + b"." + raw_body,
            hashlib.sha256,
        ).hexdigest()
    )
    return hmac.compare_digest(expected, headers["X-Webhook-Signature"])


@pytest.fixture(autouse=True)
def allow_local_webhooks(settings):
    settings.WEBHOOK_ALLOW_INSECURE_URLS = True


def make_client(**kwargs):
    options = {
        "name": "上游平台",
        "scopes": ["registrations:read"],
        "allowed_includes": ["team", "members", "members.ranks", "logs"],
    }
    options.update(kwargs)
    client, _ = api_services.create_client(**options)
    return client


def configure(client, *, events=ALL_EVENTS, mode=WebhookPayloadMode.THIN, url=None):
    client.webhook_url = url or "https://upstream.example.com/hooks"
    client.webhook_secret = "hook-secret"
    client.webhook_events = list(events)
    client.webhook_payload_mode = mode
    client.save()
    return client


def player(email, nickname, *, sjtu=True):
    now = timezone.now()
    user = User.objects.create_user(
        email=email,
        password="Correct-Horse-Battery-1",
        nickname=nickname,
        is_sjtu=sjtu,
        agreed_terms_at=now,
        agreed_cross_border_at=now,
    )
    GameAccount.objects.create(user=user, battletag=f"{nickname}#1234", rank_damage=22)
    ContactMethod.objects.create(user=user, type=ContactType.QQ, value="123456789")
    return user


def make_tournament(**kwargs):
    now = timezone.now()
    options = {
        "title": "秋季邀请赛",
        "registration_opens_at": now - timedelta(days=1),
        "registration_closes_at": now + timedelta(days=7),
        "roster_min": 2,
        "roster_max": 3,
        "status": TournamentStatus.PUBLISHED,
        "published_at": now,
        "review_mode": ReviewMode.UPSTREAM,
    }
    options.update(kwargs)
    return Tournament.objects.create(**options)


def make_team(prefix):
    captain = player(f"{prefix}-cap@example.com", f"{prefix}队长")
    mate = player(f"{prefix}-mate@example.com", f"{prefix}队员", sjtu=False)
    team = team_services.create_team(user=captain, name=f"{prefix}战队")
    application = team_services.apply_to_team(
        team=team, user=mate, roles={"tank": True}
    )
    team_services.approve_application(application=application, actor=captain)
    selections = {
        str(membership.user.pk): membership.user.game_accounts.first().pk
        for membership in team.memberships.all()
    }
    return team, captain, selections


def make_registration(tournament, prefix="钩子"):
    team, captain, selections = make_team(prefix)
    registration = reg.submit(
        tournament=tournament, team=team, actor=captain, selections=selections
    )
    return registration, team, captain, selections


def admin_user(email="hook-admin@example.com"):
    return User.objects.create_user(
        email=email,
        password="Correct-Horse-Battery-1",
        nickname="管理员",
        agreed_terms_at=timezone.now(),
        agreed_cross_border_at=timezone.now(),
    )


# --- subscription filters ------------------------------------------------------


@flow
def test_events_reach_a_subscribed_client():
    tournament = make_tournament()
    configure(make_client())
    registration, *_ = make_registration(tournament)
    WebhookDelivery.objects.all().delete()

    reg.approve(registration=registration, actor=None, actor_type="upstream")

    delivery = WebhookDelivery.objects.get()
    assert delivery.event_type == WebhookEvent.REGISTRATION_STATUS_CHANGED
    assert delivery.payload["data"]["status"] == "approved"
    assert delivery.payload["data"]["previous_status"] == "pending"
    assert delivery.payload["actor_type"] == "upstream"


@flow
def test_an_unsubscribed_event_is_not_delivered():
    tournament = make_tournament()
    configure(make_client(), events=[WebhookEvent.PING])
    registration, *_ = make_registration(tournament)
    WebhookDelivery.objects.all().delete()

    reg.approve(registration=registration, actor=None, actor_type="upstream")

    assert WebhookDelivery.objects.count() == 0


@flow
def test_an_unrelated_tournament_is_not_delivered():
    """Design 11.8.1: a local-review tournament the client did not push."""
    tournament = make_tournament()
    configure(make_client())
    registration, *_ = make_registration(tournament)
    Tournament.objects.filter(pk=tournament.pk).update(review_mode=ReviewMode.LOCAL)
    registration.refresh_from_db()
    WebhookDelivery.objects.all().delete()

    reg.approve(registration=registration, actor=admin_user())

    assert WebhookDelivery.objects.count() == 0


@flow
def test_a_client_gets_events_for_its_own_local_tournament():
    tournament = make_tournament()
    client = configure(make_client())
    registration, *_ = make_registration(tournament)
    Tournament.objects.filter(pk=tournament.pk).update(
        review_mode=ReviewMode.LOCAL, source_client=client, external_id="up-9"
    )
    registration.refresh_from_db()
    WebhookDelivery.objects.all().delete()

    reg.approve(registration=registration, actor=admin_user())

    delivery = WebhookDelivery.objects.get()
    assert delivery.payload["data"]["tournament_external_id"] == "up-9"
    assert delivery.payload["actor_type"] == "admin"


@flow
def test_a_client_without_a_url_gets_nothing():
    tournament = make_tournament()
    client = make_client()
    client.webhook_events = ALL_EVENTS
    client.save()
    registration, *_ = make_registration(tournament)
    WebhookDelivery.objects.all().delete()

    reg.approve(registration=registration, actor=None, actor_type="upstream")

    assert WebhookDelivery.objects.count() == 0


@flow
def test_a_revoked_client_gets_nothing():
    tournament = make_tournament()
    client = configure(make_client())
    registration, *_ = make_registration(tournament)
    api_services.revoke(client)
    WebhookDelivery.objects.all().delete()

    reg.approve(registration=registration, actor=None, actor_type="upstream")

    assert WebhookDelivery.objects.count() == 0


@flow
def test_external_id_is_hidden_from_other_clients():
    tournament = make_tournament()
    pusher = configure(make_client(name="推送方"))
    other = configure(make_client(name="别的上游"))
    registration, *_ = make_registration(tournament)
    Tournament.objects.filter(pk=tournament.pk).update(
        source_client=pusher, external_id="only-mine"
    )
    registration.refresh_from_db()
    WebhookDelivery.objects.all().delete()

    reg.approve(registration=registration, actor=None, actor_type="upstream")

    by_client = {row.client_id: row for row in WebhookDelivery.objects.all()}
    assert by_client[pusher.pk].payload["data"]["tournament_external_id"] == "only-mine"
    assert by_client[other.pk].payload["data"]["tournament_external_id"] is None


# --- event types ---------------------------------------------------------------


@flow
def test_submit_sync_and_withdraw_events():
    tournament = make_tournament()
    configure(make_client())
    registration, team, captain, selections = make_registration(tournament, "流程")

    assert (
        WebhookDelivery.objects.latest("id").event_type
        == WebhookEvent.REGISTRATION_SUBMITTED
    )

    reg.submit(tournament=tournament, team=team, actor=captain, selections=selections)
    assert (
        WebhookDelivery.objects.latest("id").event_type
        == WebhookEvent.REGISTRATION_ROSTER_SYNCED
    )

    registration.refresh_from_db()
    reg.withdraw(registration=registration, actor=captain)
    assert (
        WebhookDelivery.objects.latest("id").event_type
        == WebhookEvent.REGISTRATION_WITHDRAWN
    )


@pytest.mark.django_db
def test_ping_event():
    client = configure(make_client())
    delivery = webhooks.queue_ping(client)
    assert delivery.event_type == WebhookEvent.PING
    assert delivery.payload["data"]["client"] == client.name
    assert delivery.payload["id"] == str(delivery.event_id)


# --- payload shapes ------------------------------------------------------------


@flow
def test_thin_payload_has_no_registration_object():
    tournament = make_tournament()
    configure(make_client(), mode=WebhookPayloadMode.THIN)
    registration, *_ = make_registration(tournament)
    WebhookDelivery.objects.all().delete()

    reg.approve(registration=registration, actor=None, actor_type="upstream")

    data = WebhookDelivery.objects.get().payload["data"]
    assert "registration" not in data
    assert set(data) == {
        "registration_id",
        "tournament_id",
        "tournament_external_id",
        "team_id",
        "status",
        "previous_status",
        "roster_version",
    }


@flow
def test_full_payload_expands_but_never_logs():
    tournament = make_tournament()
    configure(make_client(), mode=WebhookPayloadMode.FULL)
    registration, *_ = make_registration(tournament)
    WebhookDelivery.objects.all().delete()

    reg.approve(registration=registration, actor=None, actor_type="upstream")

    payload = WebhookDelivery.objects.get().payload
    obj = payload["data"]["registration"]
    assert obj["team"]["name"] == "钩子战队"
    assert obj["members"][0]["ranks"]["damage"]["label"] == "钻石 3"
    assert "logs" not in obj  # design 11.8.2 excludes logs
    text = json.dumps(payload, ensure_ascii=False)
    assert "123456789" not in text
    assert "@example.com" not in text


@flow
def test_payload_is_frozen_at_event_time():
    """Design 12.10.3: a retry sends exactly what the first attempt sent."""
    tournament = make_tournament()
    configure(make_client())
    registration, *_ = make_registration(tournament)
    WebhookDelivery.objects.all().delete()

    reg.approve(registration=registration, actor=None, actor_type="upstream")
    delivery = WebhookDelivery.objects.get()
    assert delivery.payload["data"]["status"] == "approved"

    reg.reject(
        registration=registration,
        actor=None,
        note="后来又驳回了",
        actor_type="upstream",
    )

    delivery.refresh_from_db()
    assert delivery.payload["data"]["status"] == "approved"


@flow
def test_a_rolled_back_action_sends_nothing():
    """on_commit semantics: no commit, no event."""
    from django.db import transaction

    tournament = make_tournament()
    configure(make_client())
    team, captain, selections = make_team("回滚")
    WebhookDelivery.objects.all().delete()

    class Rollback(Exception):
        pass

    with pytest.raises(Rollback), transaction.atomic():
        reg.submit(
            tournament=tournament, team=team, actor=captain, selections=selections
        )
        raise Rollback

    assert WebhookDelivery.objects.count() == 0


# --- signing -------------------------------------------------------------------


@pytest.mark.django_db
def test_signature_matches_the_designs_verifier():
    client = configure(make_client())
    delivery = webhooks.queue_ping(client)
    body = json.dumps(delivery.payload, ensure_ascii=False).encode()
    headers = webhooks.build_headers(delivery, body)

    assert verify_webhook(headers, body, "hook-secret") is True
    assert verify_webhook(headers, body + b" ", "hook-secret") is False
    assert verify_webhook(headers, body, "wrong-secret") is False
    assert headers["X-Webhook-Id"] == str(delivery.event_id)
    assert headers["X-Webhook-Event"] == WebhookEvent.PING


@pytest.mark.django_db
def test_an_old_timestamp_fails_the_verifier():
    client = configure(make_client())
    delivery = webhooks.queue_ping(client)
    body = json.dumps(delivery.payload, ensure_ascii=False).encode()
    headers = webhooks.build_headers(delivery, body, now=time.time() - 600)
    assert verify_webhook(headers, body, "hook-secret") is False


# --- delivery outcomes ---------------------------------------------------------


def fake_post(status=None, error=""):
    def _post(url, body, headers):
        return status, error

    return _post


@pytest.mark.django_db
def test_2xx_succeeds(monkeypatch):
    delivery = webhooks.queue_ping(configure(make_client()))
    monkeypatch.setattr(webhooks, "post", fake_post(204))

    assert webhooks.attempt(delivery) is True

    delivery.refresh_from_db()
    assert delivery.status == DeliveryStatus.SUCCEEDED
    assert delivery.delivered_at is not None
    assert delivery.next_attempt_at is None
    assert delivery.last_error == ""


@pytest.mark.django_db
@pytest.mark.parametrize("status", [301, 302, 307])
def test_3xx_is_a_failure(monkeypatch, status):
    """Design 11.8.3: redirects are not followed and count as failures."""
    delivery = webhooks.queue_ping(configure(make_client()))
    monkeypatch.setattr(webhooks, "post", fake_post(status, f"HTTP {status}"))

    assert webhooks.attempt(delivery) is False

    delivery.refresh_from_db()
    assert delivery.status == DeliveryStatus.PENDING
    assert delivery.last_status_code == status


@pytest.mark.django_db
def test_a_timeout_is_a_failure(monkeypatch):
    delivery = webhooks.queue_ping(configure(make_client()))
    monkeypatch.setattr(webhooks, "post", fake_post(None, "连接失败：timed out"))

    assert webhooks.attempt(delivery) is False

    delivery.refresh_from_db()
    assert delivery.last_status_code is None
    assert "timed out" in delivery.last_error


@pytest.mark.django_db
def test_retry_schedule_and_final_failure(monkeypatch):
    delivery = webhooks.queue_ping(configure(make_client()))
    monkeypatch.setattr(webhooks, "post", fake_post(500, "HTTP 500"))

    gaps = []
    for _ in range(webhooks.MAX_ATTEMPTS - 1):
        before = timezone.now()
        webhooks.attempt(delivery)
        delivery.refresh_from_db()
        assert delivery.status == DeliveryStatus.PENDING
        gaps.append(round((delivery.next_attempt_at - before).total_seconds()))

    assert gaps == [60, 300, 1800, 7200, 21600, 43200, 86400]

    webhooks.attempt(delivery)
    delivery.refresh_from_db()
    assert delivery.attempts == 8
    assert delivery.status == DeliveryStatus.FAILED
    assert delivery.next_attempt_at is None


@pytest.mark.django_db
def test_final_failure_mails_superusers(monkeypatch):
    User.objects.create_superuser(
        email="boss@example.com",
        password="Correct-Horse-Battery-1",
        nickname="超管",
    )
    delivery = webhooks.queue_ping(configure(make_client()))
    monkeypatch.setattr(webhooks, "post", fake_post(500, "HTTP 500"))

    for _ in range(webhooks.MAX_ATTEMPTS):
        webhooks.attempt(delivery)

    delivery.refresh_from_db()
    assert delivery.status == DeliveryStatus.FAILED
    assert len(mail.outbox) == 1
    assert "boss@example.com" in mail.outbox[0].to
    assert str(delivery.event_id) in mail.outbox[0].body


@pytest.mark.django_db
def test_resend_keeps_the_event_id(monkeypatch):
    delivery = webhooks.queue_ping(configure(make_client()))
    monkeypatch.setattr(webhooks, "post", fake_post(500, "HTTP 500"))
    for _ in range(webhooks.MAX_ATTEMPTS):
        webhooks.attempt(delivery)
    delivery.refresh_from_db()
    event_id = delivery.event_id
    assert delivery.status == DeliveryStatus.FAILED

    webhooks.resend(delivery)

    delivery.refresh_from_db()
    assert delivery.event_id == event_id
    assert delivery.status == DeliveryStatus.PENDING
    assert delivery.attempts == 0


# --- url safety ----------------------------------------------------------------


@pytest.mark.django_db
@override_settings(WEBHOOK_ALLOW_INSECURE_URLS=False)
@pytest.mark.parametrize(
    "url",
    [
        "http://upstream.example.com/hooks",  # not https
        "https://127.0.0.1/hooks",  # loopback
        "https://10.0.0.5/hooks",  # private
        "https://169.254.169.254/latest/meta-data/",  # link-local metadata
    ],
)
def test_unsafe_webhook_urls_are_refused(url):
    from core.net import UnsafeUrl

    with pytest.raises(UnsafeUrl):
        webhooks.validate_webhook_url(url)


@pytest.mark.django_db
def test_delivery_rechecks_the_url_at_send_time(settings):
    """DNS can change between saving and sending, so check again."""
    client = configure(make_client(), url="https://upstream.example.com/hooks")
    delivery = webhooks.queue_ping(client)
    settings.WEBHOOK_ALLOW_INSECURE_URLS = False
    client.webhook_url = "https://127.0.0.1/hooks"
    client.save(update_fields=["webhook_url"])
    delivery.refresh_from_db()

    assert webhooks.attempt(delivery) is False

    delivery.refresh_from_db()
    assert delivery.last_status_code is None
    assert "内网" in delivery.last_error


# --- the worker task -----------------------------------------------------------


@pytest.mark.django_db
def test_task_skips_a_delivery_that_is_already_done(monkeypatch):
    delivery = webhooks.queue_ping(configure(make_client()))
    delivery.status = DeliveryStatus.SUCCEEDED
    delivery.save(update_fields=["status"])

    from integrations.tasks import deliver_webhook

    calls = []
    monkeypatch.setattr(webhooks, "attempt", lambda d: calls.append(d) or True)
    assert deliver_webhook.func(delivery.pk) == "done"
    assert calls == []


@pytest.mark.django_db
def test_task_defers_a_delivery_that_is_not_due_yet(monkeypatch):
    delivery = webhooks.queue_ping(configure(make_client()))
    delivery.next_attempt_at = timezone.now() + timedelta(hours=2)
    delivery.save(update_fields=["next_attempt_at"])

    from integrations.tasks import deliver_webhook

    calls = []
    monkeypatch.setattr(webhooks, "attempt", lambda d: calls.append(d) or True)
    assert deliver_webhook.func(delivery.pk) == "deferred"
    assert calls == []


@pytest.mark.django_db
def test_task_skips_a_revoked_client(monkeypatch):
    client = configure(make_client())
    delivery = webhooks.queue_ping(client)
    api_services.revoke(client)

    from integrations.tasks import deliver_webhook

    calls = []
    monkeypatch.setattr(webhooks, "attempt", lambda d: calls.append(d) or True)
    assert deliver_webhook.func(delivery.pk) == "skipped"
    assert calls == []


@pytest.mark.django_db
def test_task_reports_each_outcome(monkeypatch):
    from integrations.tasks import deliver_webhook

    delivery = webhooks.queue_ping(configure(make_client()))
    monkeypatch.setattr(webhooks, "post", fake_post(200))
    assert deliver_webhook.func(delivery.pk) == "succeeded"

    other = webhooks.queue_ping(configure(make_client(name="第二个")))
    monkeypatch.setattr(webhooks, "post", fake_post(500, "HTTP 500"))
    assert deliver_webhook.func(other.pk) == "retrying"

    other.refresh_from_db()
    for _ in range(webhooks.MAX_ATTEMPTS - 2):
        webhooks.attempt(other)
    other.refresh_from_db()
    other.next_attempt_at = timezone.now()
    other.save(update_fields=["next_attempt_at"])
    assert deliver_webhook.func(other.pk) == "failed"


@pytest.mark.django_db
def test_task_on_a_missing_delivery():
    from integrations.tasks import deliver_webhook

    assert deliver_webhook.func(999999) == "gone"


# --- the 24-hour tier and the safety net ---------------------------------------


@pytest.mark.django_db
def test_the_last_retry_is_scheduled_a_day_out(monkeypatch):
    """Design 11.8.3: the seventh gap is 24 hours.

    019 checked the gap sequence in isolation; this pins the value that
    actually lands in the database, which is what a worker acts on.
    """
    delivery = webhooks.queue_ping(configure(make_client()))
    monkeypatch.setattr(webhooks, "post", fake_post(500, "HTTP 500"))

    for _ in range(webhooks.MAX_ATTEMPTS - 1):
        webhooks.attempt(delivery)
        delivery.refresh_from_db()

    assert delivery.attempts == webhooks.MAX_ATTEMPTS - 1
    assert delivery.status == DeliveryStatus.PENDING
    gap = delivery.next_attempt_at - timezone.now()
    assert timedelta(hours=23, minutes=59) < gap <= timedelta(hours=24)


@pytest.mark.django_db
def test_the_safety_net_picks_up_a_delivery_whose_task_was_lost(monkeypatch):
    """Design 11.8.3: a task queued 24 hours out may not survive a restart.

    The row is the source of truth, so a due delivery with no task behind it
    still has to go out. This is the real protection for the long tiers.
    """
    from integrations.tasks import deliver_due_webhooks

    client = configure(make_client())
    delivery = WebhookDelivery.objects.create(
        client=client,
        event_type=WebhookEvent.PING,
        payload={"id": "lost", "type": "ping", "data": {}},
        status=DeliveryStatus.PENDING,
        attempts=6,
        next_attempt_at=timezone.now() - timedelta(hours=2),
    )

    picked = deliver_due_webhooks.func()

    assert picked == 1
    # And the task it queued does deliver when it runs.
    monkeypatch.setattr(webhooks, "post", fake_post(200))
    from integrations.tasks import deliver_webhook

    assert deliver_webhook.func(delivery.pk) == "succeeded"
    delivery.refresh_from_db()
    assert delivery.status == DeliveryStatus.SUCCEEDED


@pytest.mark.django_db
def test_the_safety_net_leaves_alone_what_is_not_due_yet():
    from integrations.tasks import deliver_due_webhooks

    client = configure(make_client())
    WebhookDelivery.objects.create(
        client=client,
        event_type=WebhookEvent.PING,
        payload={},
        status=DeliveryStatus.PENDING,
        attempts=6,
        next_attempt_at=timezone.now() + timedelta(hours=20),
    )

    assert deliver_due_webhooks.func() == 0


@pytest.mark.django_db
def test_the_safety_net_ignores_finished_deliveries():
    from integrations.tasks import deliver_due_webhooks

    client = configure(make_client())
    for status in (DeliveryStatus.SUCCEEDED, DeliveryStatus.FAILED):
        WebhookDelivery.objects.create(
            client=client,
            event_type=WebhookEvent.PING,
            payload={},
            status=status,
            next_attempt_at=timezone.now() - timedelta(days=3),
        )

    assert deliver_due_webhooks.func() == 0
