"""「发信」 in the back office (design 10.5, v7.8): the same page as the site's
(``core.held_views``), drawn in the back office and placed where the action
was done, so the top bar stays on that section."""

from __future__ import annotations

from urllib.parse import urlsplit

from django.shortcuts import render
from django.urls import Resolver404, resolve, reverse

from backoffice.nav import placed
from core import held_views, outbox


def _place_of(request, batch):
    """Where the action that wrote these letters sits, if it is ours."""
    row = outbox.waiting(request.user).filter(batch=batch).first()
    if row is None or not row.back:
        return None
    try:
        match = resolve(urlsplit(row.back).path)
    except Resolver404:
        return None
    return getattr(match.func, "backoffice_place", None)


@placed("home", "home")
def letters_confirm(request, batch):
    place = _place_of(request, batch)
    if place is not None:
        request.backoffice_place = place
    return held_views.confirm(
        request,
        batch,
        template="backoffice/letters/confirm.html",
        fallback=reverse("backoffice:home"),
    )


@placed("home", "home")
def letters_waiting(request):
    return render(
        request,
        "backoffice/letters/waiting.html",
        {"page_title": "还没发的信", "batches": outbox.batches(request.user)},
    )
