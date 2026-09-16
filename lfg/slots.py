"""Homepage LFG card: a count for signed-in visitors (design 13.13.3)."""

from __future__ import annotations

from django.template.loader import render_to_string


def home_lfg_slot(request, argument):
    from lfg import services

    count = None
    if getattr(request.user, "is_authenticated", False):
        count = services.open_count()
    return render_to_string(
        "slots/home_lfg.html",
        {"oob": True, "lfg_open_count": count},
        request=request,
    )
