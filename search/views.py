"""The search results page (design 13.16)."""

from __future__ import annotations

from django.shortcuts import render
from django.views.decorators.http import require_GET

from core.ratelimit import client_ip, over_limit
from search import services

SEARCH_RATE_LIMIT = 30  # per IP per minute (附录 C)


@require_GET
def search(request):
    from content.seo import absolute_uri, build_seo

    raw = request.GET.get("q", "")
    query = raw.strip()[: services.MAX_QUERY_LENGTH]
    terms = services.parse_query(raw)
    groups = []
    if terms:
        if over_limit(f"search:{client_ip(request)}", SEARCH_RATE_LIMIT, 60):
            return render(request, "errors/429.html", {"retry_after": 60}, status=429)
        groups = services.search_all(terms)
    context = {
        "query": query,
        "terms": terms,
        "groups": groups,
        "total": sum(len(group.hits) for group in groups),
        "seo": build_seo(
            request,
            title="站内搜索",
            description="搜索文章、赛事与内战、战队和成员。",
            kind="other",
            canonical=absolute_uri(request, "/search/"),
        ),
    }
    return render(request, "search/results.html", context)
