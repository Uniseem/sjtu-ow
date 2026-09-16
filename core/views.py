from django.contrib import messages
from django.core.exceptions import PermissionDenied
from django.http import HttpResponse, JsonResponse
from django.shortcuts import redirect, render
from django.template.loader import render_to_string
from django.urls import reverse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_GET, require_POST

from core.health import run_health_checks
from core.mail import SMTPNotConfigured, send_test_email
from core.models import SiteSettings


@require_GET
def home(request):
    from wagtail.models import Site

    from content.models import HomePage

    site = Site.find_for_request(request)
    if site is not None:
        page = site.root_page.specific
        if isinstance(page, HomePage) and page.live:
            return page.serve(request)
    return render(request, "core/home.html")


@csrf_exempt
@require_GET
def healthz(request):
    """Liveness/readiness probe. Does not require CSRF; returns JSON status only."""
    result = run_health_checks()
    status_code = 200 if result["ok"] else 503
    return JsonResponse(
        {"status": result["status"], "checks": result["checks"]},
        status=status_code,
    )


def _error_response(template_name, status, context=None):
    """Render an error page without RequestContext (no database)."""
    html = render_to_string(template_name, context or {})
    return HttpResponse(html, status=status, content_type="text/html; charset=utf-8")


def page_not_found(request, exception):
    return _error_response("errors/404.html", 404)


def permission_denied(request, exception):
    reason = str(exception) if exception else "你没有权限查看这个页面。"
    return _error_response("errors/403.html", 403, {"reason": reason})


def server_error(request):
    request_id = getattr(request, "request_id", "") or request.headers.get(
        "X-Request-ID", ""
    )
    return _error_response("errors/500.html", 500, {"request_id": request_id})


def too_many_requests(request, retry_after=None):
    return _error_response("errors/429.html", 429, {"retry_after": retry_after})


@require_POST
def send_site_test_email(request):
    """Send a synchronous test message to the current admin (design 3.6)."""
    if not request.user.has_perm("core.change_sitesettings"):
        raise PermissionDenied
    settings_obj = SiteSettings.load(request)
    try:
        send_test_email(request.user.email)
        messages.success(request, f"测试邮件已发送到 {request.user.email}。")
    except SMTPNotConfigured as exc:
        messages.error(request, str(exc))
    except Exception as exc:  # noqa: BLE001 — show the SMTP error in the admin
        messages.error(request, f"发送失败：{exc}")
    return redirect(
        reverse(
            "wagtailsettings:edit",
            args=["core", "sitesettings", settings_obj.pk],
        )
    )
