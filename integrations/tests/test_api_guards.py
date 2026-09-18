"""API refusals that had no test (round 059's guard sweep)."""

import base64
import hashlib
import hmac
import json
import time
from datetime import timedelta

import pytest
from django.utils import timezone

from integrations.tests.test_api_endpoints import call
from tournaments.models import RegistrationStatus, ReviewMode


def _error(response):
    return response.status_code, response.json()["error"]["code"]


# --- review -----------------------------------------------------------------------


@pytest.mark.django_db
def test_upstream_cannot_review_a_local_tournament_even_idempotently(
    client, api, registration
):
    """The idempotent shortcut must not answer 200 where the upstream has no say."""
    api_obj, secret = api
    tournament = registration.tournament
    tournament.review_mode = ReviewMode.LOCAL
    tournament.save(update_fields=["review_mode"])
    registration.__class__.objects.filter(pk=registration.pk).update(
        status=RegistrationStatus.APPROVED
    )
    response = call(
        client,
        "POST",
        f"/api/v1/registrations/{registration.pk}/review",
        api=api_obj,
        secret=secret,
        body={"action": "approve", "roster_version": registration.roster_version},
    )
    assert _error(response) == (403, "review_not_allowed")


@pytest.mark.django_db
def test_review_needs_the_roster_version(client, api, registration):
    api_obj, secret = api
    response = call(
        client,
        "POST",
        f"/api/v1/registrations/{registration.pk}/review",
        api=api_obj,
        secret=secret,
        body={"action": "approve"},
    )
    assert _error(response) == (422, "validation_error")
    # Without the check int(None) still ends in a 422, but tells the upstream
    # developer the version "must be an integer" instead of that it is missing.
    assert "缺少 roster_version" in response.json()["error"]["message"]
    registration.refresh_from_db()
    assert registration.status == RegistrationStatus.PENDING


@pytest.mark.django_db
def test_batch_review_needs_a_list(client, api):
    api_obj, secret = api
    response = call(
        client,
        "POST",
        "/api/v1/registrations/review-batch",
        api=api_obj,
        secret=secret,
        body={"items": {"id": 1}},
    )
    assert _error(response) == (422, "validation_error")


# --- things that do not exist -----------------------------------------------------


@pytest.mark.django_db
@pytest.mark.parametrize(
    "method, path",
    [
        ("GET", "/api/v1/registrations/999999"),
        ("GET", "/api/v1/registrations/999999/logs"),
        ("POST", "/api/v1/registrations/999999/review"),
        ("GET", "/api/v1/tournaments/999999/roster"),
        ("GET", "/api/v1/tournaments/999999/roster.csv"),
        ("GET", "/api/v1/tournaments/999999/stats"),
    ],
)
def test_a_missing_object_is_a_404_not_a_crash(client, api, method, path):
    api_obj, secret = api
    body = {"action": "approve", "roster_version": 1} if method == "POST" else None
    response = call(client, method, path, api=api_obj, secret=secret, body=body)
    assert _error(response) == (404, "not_found")


# --- creating a tournament ----------------------------------------------------------


def _upsert_body(**changes):
    now = timezone.now()
    body = {
        "title": "上游推的赛事",
        "summary": "摘要",
        "status": "published",
        "registration_opens_at": (now - timedelta(days=1)).isoformat(),
        "registration_closes_at": (now + timedelta(days=5)).isoformat(),
        "roster_min": 2,
        "roster_max": 6,
        "review_mode": "upstream",
    }
    body.update(changes)
    return {key: value for key, value in body.items() if value is not None}


@pytest.mark.django_db
@pytest.mark.parametrize(
    "changes",
    [
        {"review_mode": "whatever"},
        {"registration_opens_at": "下周一"},
        {"registration_closes_at": (timezone.now() - timedelta(days=3)).isoformat()},
        {"roster_min": 7, "roster_max": 6},
        {"roster_min": 0},
        {"roster_max": 21},
        {"status": "whatever"},
    ],
    ids=[
        "review_mode",
        "opens_at_not_a_time",
        "closes_before_opens",
        "min_over_max",
        "min_zero",
        "max_over_20",
        "status",
    ],
)
def test_upsert_refuses_a_bad_tournament(client, api, changes):
    api_obj, secret = api
    response = call(
        client,
        "PUT",
        "/api/v1/tournaments/external/bad-1",
        api=api_obj,
        secret=secret,
        body=_upsert_body(**changes),
    )
    assert _error(response) == (422, "validation_error")


# --- paging -----------------------------------------------------------------------


def _cursor(payload):
    return base64.urlsafe_b64encode(json.dumps(payload).encode()).decode().rstrip("=")


@pytest.mark.django_db
@pytest.mark.parametrize(
    "query, expected",
    [
        ((("cursor", _cursor({"u": "not-a-time", "i": 1})),), (400, "invalid_cursor")),
        ((("limit", "0"),), (422, "validation_error")),
        ((("updated_since", "yesterday"),), (422, "validation_error")),
    ],
    ids=["cursor_time", "limit_zero", "updated_since"],
)
def test_paging_parameters_are_checked(client, api, registration, query, expected):
    api_obj, secret = api
    response = call(
        client,
        "GET",
        "/api/v1/registrations",
        api=api_obj,
        secret=secret,
        query=query,
    )
    assert _error(response) == expected


# --- signing ------------------------------------------------------------------------


@pytest.mark.django_db
@pytest.mark.parametrize("nonce", ["short", "x" * 65])
def test_a_nonce_outside_16_to_64_characters_is_refused(client, api, nonce):
    """Design 11.2.3: a short nonce makes replays guessable."""
    api_obj, secret = api
    timestamp = str(int(time.time()))
    to_sign = "\n".join(
        ["GET", "/api/v1/ping", "", timestamp, nonce, hashlib.sha256(b"").hexdigest()]
    )
    signature = hmac.new(secret.encode(), to_sign.encode(), hashlib.sha256).hexdigest()
    response = client.get(
        "/api/v1/ping",
        headers={
            "X-Api-Key": api_obj.key_id,
            "X-Timestamp": timestamp,
            "X-Nonce": nonce,
            "X-Signature": signature,
        },
    )
    assert _error(response) == (401, "invalid_signature")
