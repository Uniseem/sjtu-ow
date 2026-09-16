"""Public sitemap and robots.txt (design 13.14)."""

from django.conf import settings
from django.http import HttpResponse
from django.shortcuts import render
from django.views.decorators.http import require_GET

from content.models import ArticlePage, StandardPage


@require_GET
def sitemap_xml(request):
    urlset = []
    for model in (ArticlePage, StandardPage):
        for page in model.objects.live().public().order_by("path"):
            loc = page.get_full_url(request) or request.build_absolute_uri(
                page.get_url(request)
            )
            urlset.append({"loc": loc, "lastmod": page.last_published_at})
    return render(
        request,
        "content/sitemap.xml",
        {"urlset": urlset},
        content_type="application/xml",
    )


@require_GET
def robots_txt(request):
    sitemap = request.build_absolute_uri("/sitemap.xml")
    if not sitemap.startswith("http"):
        sitemap = settings.SITE_URL.rstrip("/") + "/sitemap.xml"
    body = "\n".join(
        [
            "User-agent: *",
            "Disallow: /admin/",
            "Disallow: /api/",
            "Disallow: /me/",
            "Disallow: /accounts/",
            "Disallow: /_fragments/",
            f"Sitemap: {sitemap}",
            "",
        ]
    )
    return HttpResponse(body, content_type="text/plain; charset=utf-8")
