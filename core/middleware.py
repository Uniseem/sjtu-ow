"""Request-ID and Wagtail-admin CSP adjustments. These do not touch the database."""

from django.conf import settings
from django.utils.crypto import get_random_string
from django.utils.csp import CSP

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
        prefix = getattr(settings, "WAGTAILADMIN_PATH_PREFIX", "/admin/")
        if request.path.startswith(prefix):
            response._csp_config = ADMIN_CSP
        return response
