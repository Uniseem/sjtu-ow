"""Public tournament pages (design 8.2)."""

from __future__ import annotations

from django.http import Http404
from django.shortcuts import get_object_or_404, render
from django.views.decorators.http import require_GET

from tournaments import services
from tournaments.models import Tournament


@require_GET
def tournament_index(request):
    return render(
        request,
        "tournaments/index.html",
        {"groups": services.grouped_tournaments()},
    )


@require_GET
def tournament_detail(request, pk):
    tournament = get_object_or_404(Tournament.objects.select_related("cover"), pk=pk)
    if not tournament.is_public:
        raise Http404("赛事还没有发布。")
    return render(
        request,
        "tournaments/detail.html",
        {
            "tournament": tournament,
            "phase": tournament.phase(),
            "phase_label": services.PHASE_LABELS[tournament.phase()],
            "approved_teams": services.approved_teams(tournament),
        },
    )
