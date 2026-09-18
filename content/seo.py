"""Page title, description, canonical URL, and Open Graph tags (design 13.14)."""

from __future__ import annotations

from django.conf import settings

from core.models import SiteSettings

SITE_NAME = "上海交通大学守望先锋社区"
DEFAULT_DESCRIPTION = "上海交通大学守望先锋社区网站"

# Design 13.14's page kinds; each detail view passes its own.
SHARE_KINDS = ("article", "tournament", "team", "scrim", "other")


def absolute_uri(request, path: str = "") -> str:
    if path.startswith(("http://", "https://")):
        return path
    if request is not None:
        return request.build_absolute_uri(path or request.path)
    base = settings.SITE_URL.rstrip("/")
    if not path:
        return f"{base}/"
    if not path.startswith("/"):
        path = f"/{path}"
    return f"{base}{path}"


def image_absolute_url(request, image) -> str:
    if image is None:
        return ""
    rendition = image.get_rendition("fill-1200x630")
    return absolute_uri(request, rendition.url)


def canonical_url(request, page=None) -> str:
    if page is not None:
        full = page.get_full_url(request)
        if full:
            return full
        url = page.get_url(request)
        if url:
            return absolute_uri(request, url)
    if request is None:
        return absolute_uri(None, "/")
    return request.build_absolute_uri(request.path)


def build_seo(
    request,
    *,
    title: str,
    description: str | None = None,
    image=None,
    kind: str = "other",
    canonical: str | None = None,
    page=None,
) -> dict:
    """Return template context for <title>, description, canonical, and og:*.

    Design 13.14 says what each kind shows. Until round 062 only articles
    passed their own; tournament, team and scrim pages fell back to the
    site-wide defaults.
    """
    if kind not in SHARE_KINDS:
        kind = "other"
    site = SiteSettings.load(request)
    desc = (description or "").strip() or (site.site_description or "").strip()
    if not desc:
        desc = DEFAULT_DESCRIPTION
    share_image = image or site.default_share_image
    og_image = image_absolute_url(request, share_image) if share_image else ""
    canon = canonical or canonical_url(request, page)
    document_title = title if title == SITE_NAME else f"{title} · {SITE_NAME}"
    return {
        "kind": kind,
        "title": title,
        "document_title": document_title,
        "description": desc,
        "canonical": canon,
        "og_title": title,
        "og_description": desc,
        "og_image": og_image,
        "og_url": canon,
        "site_name": SITE_NAME,
    }
