"""API client management (design 11.2, 12.10.1)."""

from __future__ import annotations

import secrets

from django.utils import timezone

from integrations.models import ApiClient

KEY_PREFIX = "ak_"
KEY_BYTES = 6  # 12 hex characters, matching the design's example
SECRET_BYTES = 32


def new_key_id() -> str:
    while True:
        key_id = f"{KEY_PREFIX}{secrets.token_hex(KEY_BYTES)}"
        if not ApiClient.objects.filter(key_id=key_id).exists():
            return key_id


def new_secret() -> str:
    return secrets.token_urlsafe(SECRET_BYTES)


def create_client(*, name, scopes, allowed_includes, rate_limit_per_minute=600):
    """Returns (client, secret). The secret is shown once and never again."""
    secret = new_secret()
    client = ApiClient.objects.create(
        name=name,
        key_id=new_key_id(),
        secret=secret,
        scopes=list(scopes or []),
        allowed_includes=list(allowed_includes or []),
        rate_limit_per_minute=rate_limit_per_minute or 600,
    )
    return client, secret


def regenerate_secret(client) -> str:
    """The old secret stops working immediately (design 11.2)."""
    secret = new_secret()
    client.secret = secret
    client.save(update_fields=["secret"])
    return secret


def revoke(client) -> ApiClient:
    client.revoked_at = timezone.now()
    client.is_active = False
    client.save(update_fields=["revoked_at", "is_active"])
    return client
