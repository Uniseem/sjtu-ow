"""Default share metadata for pages that do not set ``seo`` themselves."""

from content.seo import SITE_NAME, build_seo


def seo(request):
    return {
        "seo": build_seo(request, title=SITE_NAME, kind="other"),
    }
