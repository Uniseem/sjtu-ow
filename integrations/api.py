"""Shared API plumbing: responses, errors, authentication (design 11.1–11.3)."""

from __future__ import annotations

import datetime
import time

from django.conf import settings
from django.core.cache import cache
from rest_framework import status as http_status
from rest_framework.response import Response
from rest_framework.views import APIView

from core.ratelimit import client_ip
from integrations.models import ApiClient, ApiRequestLog
from integrations.signing import string_to_sign, verify

ERRORS = {
    "missing_auth": (401, "缺少认证请求头"),
    "invalid_api_key": (401, "Key ID 无效或客户端已停用"),
    "timestamp_expired": (401, "时间戳与服务器时间相差过大"),
    "nonce_reused": (401, "Nonce 已经使用过"),
    "invalid_signature": (401, "签名不正确"),
    "scope_denied": (403, "没有这个接口的授权范围"),
    "include_not_allowed": (403, "没有这个展开项的权限"),
    "rate_limited": (429, "调用过于频繁"),
    "not_found": (404, "对象不存在"),
    "validation_error": (400, "请求内容不合法"),
}
NONCE_PREFIX = "sjtu_ow:api_nonce:"
RATE_PREFIX = "api"


class ApiError(Exception):
    def __init__(self, code: str, message: str = "", details=None):
        self.code = code
        default_status, default_message = ERRORS.get(code, (400, "请求失败"))
        self.status_code = default_status
        self.message = message or default_message
        self.details = details or {}
        super().__init__(self.message)


def error_response(code: str, message: str = "", details=None) -> Response:
    error = ApiError(code, message, details)
    body = {"error": {"code": error.code, "message": error.message}}
    if error.details:
        body["error"]["details"] = error.details
    return Response(body, status=error.status_code)


def data_response(data, *, status_code=200) -> Response:
    return Response({"data": data}, status=status_code)


def list_response(items, *, next_cursor=None, has_more=False) -> Response:
    return Response({"data": items, "next_cursor": next_cursor, "has_more": has_more})


def exception_handler(exc, context):
    from rest_framework.views import exception_handler as drf_handler

    if isinstance(exc, ApiError):
        return error_response(exc.code, exc.message, exc.details)
    response = drf_handler(exc, context)
    if response is not None and "error" not in (response.data or {}):
        code = "validation_error"
        if response.status_code == http_status.HTTP_404_NOT_FOUND:
            code = "not_found"
        response.data = {
            "error": {"code": code, "message": str(response.data)},
        }
    return response


def isoformat(value) -> str | None:
    """Design 11.1: ISO 8601 in UTC with a trailing Z."""
    if value is None:
        return None
    return (
        value.astimezone(datetime.UTC)
        .isoformat(timespec="seconds")
        .replace("+00:00", "Z")
    )


def _query_pairs(request):
    """Every name/value pair, repeats included, as the signature expects."""
    return [
        (name, value) for name in request.GET for value in request.GET.getlist(name)
    ]


def authenticate(request) -> ApiClient:
    """The seven checks from design 11.2.3, in order."""
    key_id = request.headers.get("X-Api-Key", "")
    timestamp = request.headers.get("X-Timestamp", "")
    nonce = request.headers.get("X-Nonce", "")
    signature = request.headers.get("X-Signature", "")
    if not all([key_id, timestamp, nonce, signature]):
        raise ApiError("missing_auth")

    client = ApiClient.objects.filter(key_id=key_id).first()
    if client is None or not client.usable:
        raise ApiError("invalid_api_key")

    try:
        skew = abs(time.time() - int(timestamp))
    except (TypeError, ValueError) as exc:
        raise ApiError("timestamp_expired") from exc
    if skew > getattr(settings, "API_TIMESTAMP_TOLERANCE", 300):
        raise ApiError("timestamp_expired")

    if not (16 <= len(nonce) <= 64):
        raise ApiError("invalid_signature", "Nonce 长度必须在 16 到 64 之间")
    nonce_key = f"{NONCE_PREFIX}{client.pk}:{nonce}"
    if not cache.add(nonce_key, 1, getattr(settings, "API_NONCE_TTL", 600)):
        raise ApiError("nonce_reused")

    payload = string_to_sign(
        method=request.method,
        path=request.path,
        query_pairs=_query_pairs(request),
        timestamp=timestamp,
        nonce=nonce,
        body=request.body,
    )
    if not verify(client.secret, payload, signature):
        raise ApiError("invalid_signature")
    return client


def check_rate(client) -> None:
    from core.ratelimit import over_limit

    limit = int(client.rate_limit_per_minute or 600)
    if over_limit(f"{RATE_PREFIX}:{client.pk}", limit, 60):
        raise ApiError("rate_limited")


def check_includes(client, includes) -> list[str]:
    """Expand and validate ``include`` (design 11.3)."""
    wanted = []
    for name in includes:
        name = name.strip()
        if not name:
            continue
        if name == "members.ranks" and "members" not in wanted:
            wanted.append("members")
        if not client.allows_include(name):
            raise ApiError("include_not_allowed", f"没有展开项「{name}」的权限")
        if name not in wanted:
            wanted.append(name)
    return wanted


class SignedApiView(APIView):
    """Base view: signature, scope and rate limit before anything else."""

    required_scope: str | None = None
    authentication_classes: list = []
    permission_classes: list = []

    def initial(self, request, *args, **kwargs):
        super().initial(request, *args, **kwargs)
        client = authenticate(request)
        request.api_client = client
        # The logging middleware sees the plain HttpRequest, not DRF's wrapper.
        getattr(request, "_request", request).api_client = client
        if self.required_scope and not client.has_scope(self.required_scope):
            raise ApiError("scope_denied", f"需要授权范围 {self.required_scope}")
        check_rate(client)
        client.touch()

    def includes(self, request) -> list[str]:
        raw = request.GET.get("include", "")
        return check_includes(request.api_client, raw.split(",") if raw else [])


def log_request(request, response, *, started_at) -> None:
    """One row per call, no bodies (design 12.10.2)."""
    client = getattr(request, "api_client", None)
    error_code = ""
    body = getattr(response, "data", None)
    if isinstance(body, dict) and isinstance(body.get("error"), dict):
        error_code = body["error"].get("code", "")[:64]
    path = request.get_full_path()
    ApiRequestLog.objects.create(
        client=client if getattr(client, "pk", None) else None,
        request_id=getattr(request, "request_id", "") or "",
        method=request.method[:8],
        path=path[:500],
        status_code=response.status_code,
        error_code=error_code,
        ip=client_ip(request)[:64],
        duration_ms=int((time.monotonic() - started_at) * 1000),
    )
