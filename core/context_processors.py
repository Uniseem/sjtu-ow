"""Values every template needs: fonts (13.12.4), environment (16.10), the
default cover pool (13.2.5) and the default avatar pool (details 2.4)."""

from django.conf import settings

from core.models import SiteSettings


def fonts(request):
    settings_obj = SiteSettings.load(request_or_site=request)
    return {"font_css_url": settings_obj.font_css_path or ""}


def site_environment(request):
    return {"test_environment": settings.TEST_ENVIRONMENT}


def cover_pool(request):
    """The 默认封面 pool, loaded at most once per page (13.2.5, v6.7)."""
    from core.covers import lazy_pool

    return {"cover_pool": lazy_pool()}


def avatar_pool(request):
    """The 默认头像 pool, loaded at most once per page (details 2.4, v6.9)."""
    from core.avatars import lazy_pool

    return {"avatar_pool": lazy_pool()}
