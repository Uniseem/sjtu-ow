"""Small cache-backed rate limiter (design 附录 C)."""

from __future__ import annotations

import time

from django.core.cache import cache


def client_ip(request) -> str:
    """The visitor's address. Caddy appends it to X-Forwarded-For."""
    forwarded = request.headers.get("X-Forwarded-For", "")
    if forwarded:
        return forwarded.split(",")[-1].strip()
    return request.META.get("REMOTE_ADDR", "")


def over_limit(key: str, limit: int, window_seconds: int = 60) -> bool:
    """Count one hit; True once the caller has used up its quota."""
    bucket = int(time.time() // window_seconds)
    cache_key = f"sjtu_ow:rl:{key}:{bucket}"
    try:
        added = cache.add(cache_key, 1, window_seconds * 2)
        count = 1 if added else cache.incr(cache_key)
    except ValueError:  # entry expired between add() and incr()
        cache.set(cache_key, 1, window_seconds * 2)
        count = 1
    return count > limit
