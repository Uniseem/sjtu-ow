"""Request ID, hint cookies, admin CSP, and the prerender fallback."""

import logging

from django.conf import settings
from django.utils.crypto import get_random_string
from django.utils.csp import CSP

logger = logging.getLogger(__name__)

OW_LOGGED_IN_COOKIE = "ow_logged_in"
OW_FLASH_COOKIE = "ow_flash"

ADMIN_CSP = {
    "default-src": [CSP.SELF],
    "script-src": [CSP.SELF, CSP.UNSAFE_INLINE, CSP.UNSAFE_EVAL],
    "style-src": [CSP.SELF, CSP.UNSAFE_INLINE],
    "img-src": [CSP.SELF, "data:", "blob:"],
    "font-src": [CSP.SELF, "data:"],
    "connect-src": [CSP.SELF],
    "frame-ancestors": [CSP.SELF],
}


class RequestIDMiddleware:
    """Attach a request ID for the 500 error page. No database access."""

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        request_id = request.headers.get("X-Request-ID") or get_random_string(12)
        request.request_id = request_id
        response = self.get_response(request)
        response["X-Request-ID"] = request_id
        return response


class WagtailAdminCSPMiddleware:
    """Relax CSP for the Wagtail admin path (design 15.2) before headers are written."""

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        response = self.get_response(request)
        prefix = getattr(settings, "ADMIN_URL_PREFIX", "/admin/")
        if request.path.startswith(prefix):
            response._csp_config = ADMIN_CSP
        return response


class LoggedInHintCookieMiddleware:
    """Set the two hint cookies read by prerendered pages (design 13.13.3).

    Neither cookie holds identity data. The page script reads them, so they are
    not HttpOnly. ``ow_logged_in`` lives as long as the session; ``ow_flash``
    says "there is a message waiting" and is dropped once it is shown.
    """

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        response = self.get_response(request)
        user = getattr(request, "user", None)
        if user is not None and user.is_authenticated:
            response.set_cookie(
                OW_LOGGED_IN_COOKIE,
                "1",
                max_age=settings.SESSION_COOKIE_AGE,
                httponly=False,
                samesite=settings.SESSION_COOKIE_SAMESITE,
                secure=getattr(settings, "SESSION_COOKIE_SECURE", False),
            )
        elif request.COOKIES.get(OW_LOGGED_IN_COOKIE):
            response.delete_cookie(
                OW_LOGGED_IN_COOKIE,
                samesite=settings.SESSION_COOKIE_SAMESITE,
            )
        self._flash_cookie(request, response)
        return response

    @staticmethod
    def _flash_cookie(request, response):
        storage = getattr(request, "_messages", None)
        if storage is None:
            return
        if getattr(storage, "added_new", False):
            response.set_cookie(
                OW_FLASH_COOKIE,
                "1",
                httponly=False,
                samesite=settings.SESSION_COOKIE_SAMESITE,
                secure=getattr(settings, "SESSION_COOKIE_SECURE", False),
            )
        elif getattr(storage, "used", False) and request.COOKIES.get(OW_FLASH_COOKIE):
            response.delete_cookie(
                OW_FLASH_COOKIE,
                samesite=settings.SESSION_COOKIE_SAMESITE,
            )


class PrerenderMissMiddleware:
    """Queue a static page when an anonymous visitor hits one we do not have.

    Caddy serves the file when it exists (design 13.13.2), so a request that
    reaches Django for a prerenderable path means the file is missing. The
    visitor still gets a live-rendered page; only the next one is faster.
    """

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        response = self.get_response(request)
        try:
            self.maybe_queue(request, response)
        except Exception:  # noqa: BLE001 — never break a page over this
            logger.warning("预渲染兜底排队失败 %s", request.path, exc_info=True)
        return response

    @staticmethod
    def maybe_queue(request, response):
        from core import prerender

        if not prerender.is_enabled():
            return
        if request.method != "GET" or request.META.get("QUERY_STRING"):
            return
        if request.headers.get(prerender.PRERENDER_HEADER):
            return  # this is the generator rendering the page right now
        if response.status_code != 200:
            return
        if "text/html" not in response.headers.get("Content-Type", ""):
            return
        user = getattr(request, "user", None)
        if user is not None and user.is_authenticated:
            return
        path = request.path
        if not prerender.looks_prerenderable(path):
            return
        targets = prerender.cached_targets()
        kind = targets.get(prerender.normalize_path(path))
        if kind and not prerender.file_for(path).exists():
            prerender.request_page(path, kind=kind)
