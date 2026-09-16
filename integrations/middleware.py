"""Log every API call and make sure the request id is visible (design 11.1)."""

from __future__ import annotations

import time

API_PREFIX = "/api/"


class ApiRequestLogMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        if not request.path.startswith(API_PREFIX):
            return self.get_response(request)
        started_at = time.monotonic()
        response = self.get_response(request)
        try:
            from integrations.api import log_request

            log_request(request, response, started_at=started_at)
        except Exception:  # noqa: BLE001 — logging must never break a response
            import logging

            logging.getLogger(__name__).warning("API 调用日志写入失败", exc_info=True)
        return response
