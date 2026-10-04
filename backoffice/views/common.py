"""Small helpers the back-office pages share."""

from __future__ import annotations

from django.core.paginator import Paginator
from django.utils.http import url_has_allowed_host_and_scheme


def paginate(request, items, per_page: int):
    """One page of ``items`` and the query string to keep on the pager."""
    page_obj = Paginator(items, per_page).get_page(request.GET.get("page") or 1)
    query = request.GET.copy()
    query.pop("page", None)
    return page_obj, query.urlencode()


def search_text(request, name: str = "q", limit: int = 50) -> str:
    return (request.GET.get(name) or "").strip()[:limit]


def safe_next(request, default: str) -> str:
    """Where to go after a form, if the page asked and it is on this site."""
    wanted = request.POST.get("next") or request.GET.get("next") or ""
    if wanted and url_has_allowed_host_and_scheme(
        wanted, allowed_hosts={request.get_host()}, require_https=request.is_secure()
    ):
        return wanted
    return default
