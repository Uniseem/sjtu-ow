"""Expose the generated font stylesheet to every template (design 13.12.4)."""

from core.models import SiteSettings


def fonts(request):
    settings_obj = SiteSettings.load(request_or_site=request)
    return {"font_css_url": settings_obj.font_css_path or ""}
