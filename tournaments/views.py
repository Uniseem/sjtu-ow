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
    from content.models import ArticlePage

    articles = (
        ArticlePage.objects.live()
        .public()
        .filter(tournament=tournament)
        .order_by("-first_published_at")
    )
    from tournaments.slots import actions_context

    context = {
        "articles": articles,
        "phase": tournament.phase(),
        "phase_label": services.PHASE_LABELS[tournament.phase()],
        "approved_teams": services.approved_teams(tournament),
    }
    # Same context the fragment uses, so a live page and a filled static page
    # show the same entry (design 13.13.3).
    context.update(actions_context(request, tournament))
    return render(request, "tournaments/detail.html", context)
