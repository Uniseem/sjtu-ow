"""Small cache-backed rate limiter (design 附录 C)."""

from __future__ import annotations

import time

from django.core.cache import cache
from django.db import transaction


def client_ip(request) -> str:
    """The visitor's address. Caddy works it out, honouring the reverse
    proxies it trusts, and sends it as X-Real-IP in place of any the visitor
    sent (deploy/Caddyfile, round 120). The last X-Forwarded-For entry used
    here before is the outer proxy once there is one. Without Caddy
    (development) it is REMOTE_ADDR."""
    return request.headers.get("X-Real-IP", "").strip() or request.META.get(
        "REMOTE_ADDR", ""
    )


def over_limit(key: str, limit: int, window_seconds: int = 60) -> bool:
    """Count one hit; True once the caller has used up its quota."""
    bucket = int(time.time() // window_seconds)
    cache_key = f"sjtu_ow:rl:{key}:{bucket}"
    # The database cache has no incr of its own: Django's fallback is get
    # then set, so two requests at once both read 2 and both write 3 (216,
    # A10). In one transaction they cannot: every write transaction here is
    # IMMEDIATE (design 12.12), so the second waits for the first to commit.
    with transaction.atomic():
        try:
            added = cache.add(cache_key, 1, window_seconds * 2)
            count = 1 if added else cache.incr(cache_key)
        except ValueError:  # entry expired between add() and incr()
            cache.set(cache_key, 1, window_seconds * 2)
            count = 1
    return count > limit
