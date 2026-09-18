"""Values every template needs: fonts (13.12.4), environment (16.10)."""

from django.conf import settings

from core.models import SiteSettings


def fonts(request):
    settings_obj = SiteSettings.load(request_or_site=request)
    return {"font_css_url": settings_obj.font_css_path or ""}


def site_environment(request):
    return {"test_environment": settings.TEST_ENVIRONMENT}
