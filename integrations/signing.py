"""HMAC request signing, exactly as published to upstreams (design 11.2.2)."""

from __future__ import annotations

import hashlib
import hmac
from urllib.parse import quote


def canonical_query(query_pairs) -> str:
    """Sort by decoded name then value, then percent-encode (RFC 3986)."""
    pairs = sorted((str(name), str(value)) for name, value in query_pairs)
    return "&".join(
        f"{quote(name, safe='-_.~')}={quote(value, safe='-_.~')}"
        for name, value in pairs
    )


def body_digest(body: bytes) -> str:
    return hashlib.sha256(body or b"").hexdigest()


def string_to_sign(*, method, path, query_pairs, timestamp, nonce, body) -> str:
    return "\n".join(
        [
            method.upper(),
            path,
            canonical_query(query_pairs),
            str(timestamp),
            nonce,
            body_digest(body),
        ]
    )


def sign(secret: str, payload: str) -> str:
    return hmac.new(
        secret.encode("utf-8"), payload.encode("utf-8"), hashlib.sha256
    ).hexdigest()


def verify(secret: str, payload: str, signature: str) -> bool:
    return hmac.compare_digest(sign(secret, payload), (signature or "").lower())
