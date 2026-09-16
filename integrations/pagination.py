"""Cursor pagination for the open API (design 11.4)."""

from __future__ import annotations

import base64
import binascii
import json

from django.utils.dateparse import parse_datetime

from integrations.api import ApiError

DEFAULT_LIMIT = 50
MAX_LIMIT = 200


def encode_cursor(updated_at, pk) -> str:
    raw = json.dumps(
        {"u": updated_at.isoformat(), "i": pk}, separators=(",", ":")
    ).encode()
    return base64.urlsafe_b64encode(raw).decode().rstrip("=")


def decode_cursor(cursor: str):
    padding = "=" * (-len(cursor) % 4)
    try:
        payload = json.loads(base64.urlsafe_b64decode(cursor + padding))
        moment = parse_datetime(payload["u"])
        pk = int(payload["i"])
    except (ValueError, KeyError, TypeError, binascii.Error) as exc:
        raise ApiError("validation_error", "cursor 不合法") from exc
    if moment is None:
        raise ApiError("validation_error", "cursor 不合法")
    return moment, pk


def read_limit(request) -> int:
    raw = request.GET.get("limit")
    if not raw:
        return DEFAULT_LIMIT
    try:
        limit = int(raw)
    except ValueError as exc:
        raise ApiError("validation_error", "limit 必须是整数") from exc
    if limit < 1:
        raise ApiError("validation_error", "limit 必须大于 0")
    return min(limit, MAX_LIMIT)


def apply_updated_since(queryset, request):
    raw = request.GET.get("updated_since")
    if not raw:
        return queryset
    moment = parse_datetime(raw)
    if moment is None:
        raise ApiError("validation_error", "updated_since 必须是 ISO 8601 时间")
    return queryset.filter(updated_at__gte=moment)


def paginate(queryset, request):
    """Order by (updated_at, id) so incremental syncing never skips a row."""
    from django.db.models import Q

    queryset = apply_updated_since(queryset, request).order_by("updated_at", "id")
    cursor = request.GET.get("cursor")
    if cursor:
        moment, pk = decode_cursor(cursor)
        queryset = queryset.filter(
            Q(updated_at__gt=moment) | Q(updated_at=moment, id__gt=pk)
        )
    limit = read_limit(request)
    rows = list(queryset[: limit + 1])
    has_more = len(rows) > limit
    rows = rows[:limit]
    next_cursor = (
        encode_cursor(rows[-1].updated_at, rows[-1].pk) if has_more and rows else None
    )
    return rows, next_cursor, has_more
