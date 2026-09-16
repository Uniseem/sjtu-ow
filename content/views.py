"""Public sitemap and robots.txt (design 13.14)."""

from django.conf import settings
from django.http import HttpResponse
from django.shortcuts import redirect, render
from django.urls import reverse
from django.utils.http import urlencode
from django.views.decorators.http import require_GET

from accounts.models import Feature
from accounts.permissions import can_use
from accounts.services import (
    GROUP_SUBMITTER,
    email_is_verified,
    sync_submitter_group,
)
from content.models import ArticlePage, StandardPage
from content.services import article_create_admin_url


@require_GET
def sitemap_xml(request):
    from teams.models import Team

    urlset = []
    for model in (ArticlePage, StandardPage):
        for page in model.objects.live().public().order_by("path"):
            loc = page.get_full_url(request) or request.build_absolute_uri(
                page.get_url(request)
            )
            urlset.append({"loc": loc, "lastmod": page.last_published_at})
    # Disbanded teams stay out of the sitemap (design 13.14).
    for team in Team.objects.filter(disbanded_at__isnull=True).order_by("pk"):
        urlset.append(
            {
                "loc": request.build_absolute_uri(team.get_absolute_url()),
                "lastmod": team.updated_at,
            }
        )
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


@require_GET
def submit_entry(request):
    """Front-end 投稿 entry: redirect to admin create, or explain why not (5.4.3)."""
    user = request.user
    reasons = []
    login_url = ""
    if not user.is_authenticated:
        reasons = ["未登录"]
        next_query = urlencode({"next": "/submit/"})
        login_url = f"{reverse('account_login')}?{next_query}"
    else:
        if not email_is_verified(user):
            reasons.append("邮箱未验证")
        if not can_use(user, Feature.ARTICLE_SUBMIT):
            reasons.append("没有投稿权限")
        if not reasons:
            sync_submitter_group(user)
            if user.groups.filter(name=GROUP_SUBMITTER).exists():
                create_url = article_create_admin_url()
                if create_url:
                    return redirect(create_url)
            reasons.append("没有投稿权限")
    return render(
        request,
        "content/submit.html",
        {"reasons": reasons, "login_url": login_url},
    )
