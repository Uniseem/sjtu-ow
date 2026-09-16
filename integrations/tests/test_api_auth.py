import hashlib
import hmac
import json
import secrets
import time
from urllib.parse import quote

import pytest
from django.core.cache import cache
from django.urls import reverse
from django.utils import timezone

from integrations import services
from integrations.models import ApiClient, ApiRequestLog

# --- the signing helper published to upstreams (design 11.2.2, verbatim) ------


def sign_request(method, path, query_pairs, body, key_id, secret):
    """query_pairs 是 [(名, 值), ...]，body 是 bytes。"""
    timestamp = str(int(time.time()))
    nonce = secrets.token_hex(16)
    canonical_query = "&".join(
        f"{quote(name, safe='-_.~')}={quote(value, safe='-_.~')}"
        for name, value in sorted((str(n), str(v)) for n, v in query_pairs)
    )
    string_to_sign = "\n".join(
        [
            method.upper(),
            path,
            canonical_query,
            timestamp,
            nonce,
            hashlib.sha256(body).hexdigest(),
        ]
    )
    signature = hmac.new(
        secret.encode(), string_to_sign.encode(), hashlib.sha256
    ).hexdigest()
    return {
        "X-Api-Key": key_id,
        "X-Timestamp": timestamp,
        "X-Nonce": nonce,
        "X-Signature": signature,
    }


def headers_for(
    client_obj,
    secret,
    method="GET",
    path="/api/v1/ping",
    query=(),
    body=b"",
):
    raw = sign_request(method, path, query, body, client_obj.key_id, secret)
    return {key: value for key, value in raw.items()}


@pytest.fixture
def api_client(db):
    cache.clear()
    client_obj, secret = services.create_client(
        name="某某赛事平台",
        scopes=["tournaments:read", "registrations:read"],
        allowed_includes=["team", "members"],
    )
    return client_obj, secret


# --- the seven checks ----------------------------------------------------------


@pytest.mark.django_db
def test_ping_with_a_correct_signature(client, api_client):
    client_obj, secret = api_client
    response = client.get("/api/v1/ping", headers=headers_for(client_obj, secret))
    assert response.status_code == 200
    data = response.json()["data"]
    assert data["client"] == "某某赛事平台"
    assert data["scopes"] == ["tournaments:read", "registrations:read"]
    assert data["allowed_includes"] == ["team", "members"]
    assert data["server_time"].endswith("Z")
    assert response.headers["X-Request-ID"]


@pytest.mark.django_db
def test_missing_headers(client, api_client):
    response = client.get("/api/v1/ping")
    assert response.status_code == 401
    assert response.json()["error"]["code"] == "missing_auth"


@pytest.mark.django_db
def test_unknown_key(client, api_client):
    client_obj, secret = api_client
    headers = headers_for(client_obj, secret)
    headers["X-Api-Key"] = "ak_doesnotexist"
    response = client.get("/api/v1/ping", headers=headers)
    assert response.json()["error"]["code"] == "invalid_api_key"


@pytest.mark.django_db
def test_revoked_client(client, api_client):
    client_obj, secret = api_client
    services.revoke(client_obj)
    response = client.get("/api/v1/ping", headers=headers_for(client_obj, secret))
    assert response.json()["error"]["code"] == "invalid_api_key"


@pytest.mark.django_db
def test_stale_timestamp(client, api_client):
    client_obj, secret = api_client
    headers = headers_for(client_obj, secret)
    headers["X-Timestamp"] = str(int(time.time()) - 3600)
    response = client.get("/api/v1/ping", headers=headers)
    assert response.json()["error"]["code"] == "timestamp_expired"


@pytest.mark.django_db
def test_nonce_cannot_be_reused(client, api_client):
    client_obj, secret = api_client
    headers = headers_for(client_obj, secret)
    assert client.get("/api/v1/ping", headers=headers).status_code == 200
    response = client.get("/api/v1/ping", headers=headers)
    assert response.json()["error"]["code"] == "nonce_reused"


@pytest.mark.django_db
def test_bad_signature(client, api_client):
    client_obj, secret = api_client
    headers = headers_for(client_obj, secret)
    headers["X-Signature"] = "0" * 64
    response = client.get("/api/v1/ping", headers=headers)
    assert response.json()["error"]["code"] == "invalid_signature"


@pytest.mark.django_db
def test_signature_covers_the_query_string(client, api_client):
    client_obj, secret = api_client
    headers = headers_for(client_obj, secret, path="/api/v1/ping", query=[("a", "1")])
    # Signed for ?a=1 but sent with ?a=2
    response = client.get("/api/v1/ping?a=2", headers=headers)
    assert response.json()["error"]["code"] == "invalid_signature"


@pytest.mark.django_db
def test_signature_covers_the_body(client, api_client):
    client_obj, secret = api_client
    body = json.dumps({"x": 1}).encode()
    headers = headers_for(
        client_obj, secret, method="POST", path="/api/v1/ping", body=body
    )
    response = client.post(
        "/api/v1/ping",
        data=json.dumps({"x": 2}),
        content_type="application/json",
        headers=headers,
    )
    assert response.json()["error"]["code"] == "invalid_signature"


@pytest.mark.django_db
def test_rate_limit(client, api_client, settings):
    client_obj, secret = api_client
    ApiClient.objects.filter(pk=client_obj.pk).update(rate_limit_per_minute=2)
    client_obj.refresh_from_db()
    codes = []
    for _ in range(3):
        response = client.get("/api/v1/ping", headers=headers_for(client_obj, secret))
        codes.append(response.status_code)
    assert codes[:2] == [200, 200]
    assert codes[2] == 429


@pytest.mark.django_db
def test_regenerating_the_secret_invalidates_the_old_one(client, api_client):
    client_obj, secret = api_client
    new_secret = services.regenerate_secret(client_obj)
    assert new_secret != secret
    old = client.get("/api/v1/ping", headers=headers_for(client_obj, secret))
    assert old.json()["error"]["code"] == "invalid_signature"
    fresh = client.get("/api/v1/ping", headers=headers_for(client_obj, new_secret))
    assert fresh.status_code == 200


# --- helpers -------------------------------------------------------------------


def test_canonical_query_sorts_and_encodes():
    from integrations.signing import canonical_query

    assert canonical_query([]) == ""
    assert canonical_query([("b", "2"), ("a", "1")]) == "a=1&b=2"
    assert canonical_query([("a", "1"), ("a", "0")]) == "a=0&a=1"
    encoded = "q=%E4%B8%AD%E6%96%87%20%E7%A9%BA%E6%A0%BC"
    assert canonical_query([("q", "中文 空格")]) == encoded
    assert canonical_query([("k", "a~b-c_d.e")]) == "k=a~b-c_d.e"


def test_string_to_sign_matches_the_published_recipe():
    from integrations.signing import string_to_sign

    payload = string_to_sign(
        method="get",
        path="/api/v1/ping",
        query_pairs=[("b", "2"), ("a", "1")],
        timestamp="1700000000",
        nonce="n" * 16,
        body=b"",
    )
    assert payload.split("\n") == [
        "GET",
        "/api/v1/ping",
        "a=1&b=2",
        "1700000000",
        "n" * 16,
        hashlib.sha256(b"").hexdigest(),
    ]


# --- scopes and includes -------------------------------------------------------


@pytest.mark.django_db
def test_scope_and_include_checks(api_client):
    from integrations.api import ApiError, check_includes

    client_obj, _secret = api_client
    assert client_obj.has_scope("tournaments:read") is True
    assert client_obj.has_scope("registrations:review") is False

    assert check_includes(client_obj, ["team"]) == ["team"]
    with pytest.raises(ApiError) as exc:
        check_includes(client_obj, ["logs"])
    assert exc.value.code == "include_not_allowed"


@pytest.mark.django_db
def test_scope_denied_uses_the_right_code(client, api_client, monkeypatch):
    from integrations import views

    monkeypatch.setattr(views.PingView, "required_scope", "registrations:review")
    client_obj, secret = api_client
    response = client.get("/api/v1/ping", headers=headers_for(client_obj, secret))
    assert response.status_code == 403
    assert response.json()["error"]["code"] == "scope_denied"


# --- logging -------------------------------------------------------------------


@pytest.mark.django_db
def test_every_call_is_logged(client, api_client):
    client_obj, secret = api_client
    client.get("/api/v1/ping", headers=headers_for(client_obj, secret))
    client.get("/api/v1/ping")  # missing auth
    logs = list(ApiRequestLog.objects.order_by("created_at"))
    assert len(logs) == 2
    assert logs[0].client_id == client_obj.pk
    assert logs[0].status_code == 200
    assert logs[0].error_code == ""
    assert logs[1].client_id is None
    assert logs[1].error_code == "missing_auth"
    assert all(log.request_id for log in logs)


@pytest.mark.django_db
def test_last_used_is_updated(client, api_client):
    client_obj, secret = api_client
    assert client_obj.last_used_at is None
    client.get("/api/v1/ping", headers=headers_for(client_obj, secret))
    client_obj.refresh_from_db()
    assert client_obj.last_used_at is not None


# --- admin ---------------------------------------------------------------------


@pytest.mark.django_db
def test_admin_is_superuser_only(client, api_client, django_user_model):
    user = django_user_model.objects.create_user(
        email="plain-api@example.com",
        password="Correct-Horse-Battery-1",
        nickname="路人",
        agreed_terms_at=timezone.now(),
        agreed_cross_border_at=timezone.now(),
    )
    client.force_login(user)
    assert client.get(reverse("api_client_index")).status_code == 302

    admin = django_user_model.objects.create_superuser(
        email="admin-api@example.com",
        password="Correct-Horse-Battery-1",
        nickname="超管",
        agreed_terms_at=timezone.now(),
        agreed_cross_border_at=timezone.now(),
    )
    client.force_login(admin)
    assert client.get(reverse("api_client_index")).status_code == 200


@pytest.mark.django_db
def test_secret_is_shown_once(client, django_user_model):
    admin = django_user_model.objects.create_superuser(
        email="admin-once@example.com",
        password="Correct-Horse-Battery-1",
        nickname="超管",
        agreed_terms_at=timezone.now(),
        agreed_cross_border_at=timezone.now(),
    )
    client.force_login(admin)
    response = client.post(
        reverse("api_client_create"),
        {
            "name": "新上游",
            "scopes": ["tournaments:read"],
            "allowed_includes": ["team"],
            "rate_limit_per_minute": "600",
        },
        follow=True,
    )
    created = ApiClient.objects.get(name="新上游")
    first = response.content.decode()
    assert "只显示这一次" in first
    assert created.key_id in first
    # Reloading the page must not show it again.
    second = client.get(reverse("api_client_index")).content.decode()
    assert "只显示这一次" not in second


@pytest.mark.django_db
def test_secret_is_stored_encrypted(api_client):
    from django.db import connection

    client_obj, secret = api_client
    with connection.cursor() as cursor:
        cursor.execute(
            "SELECT secret FROM integrations_apiclient WHERE id = %s",
            [client_obj.pk],
        )
        raw = cursor.fetchone()[0]
    assert secret not in raw
    assert raw.startswith("gAAAAA")
