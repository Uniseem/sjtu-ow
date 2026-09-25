"""Public tournament pages (design 8.2)."""

from __future__ import annotations

from django.http import Http404
from django.shortcuts import get_object_or_404, render
from django.views.decorators.http import require_GET

from tournaments import services
from tournaments.models import Tournament


@require_GET
def tournament_index(request):
    groups = services.grouped_tournaments()
    listed = [item for _phase, _label, items in groups for item in items]
    return render(
        request,
        "tournaments/index.html",
        {
            "groups": groups,
            # Design 13.2.8: the night page head counts each phase.
            "phase_counts": [(label, len(items)) for _phase, label, items in groups],
            "approved_counts": services.approved_counts(listed),
            "any_listed": bool(listed),
        },
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
    from content.seo import absolute_uri, build_seo
    from tournaments.slots import actions_context

    context = {
        # Design 13.14: name, summary, cover.
        "seo": build_seo(
            request,
            title=tournament.title,
            description=tournament.summary,
            image=tournament.cover,
            kind="tournament",
            canonical=absolute_uri(request, tournament.get_absolute_url()),
        ),
        "articles": articles,
        "phase": tournament.phase(),
        "phase_label": services.PHASE_LABELS[tournament.phase()],
        "approved_teams": services.approved_teams(tournament),
    }
    if tournament.allow_individual_signup:
        from tournaments import registration as registration_service

        pool = registration_service.individual_pool(tournament)
        context["pool"] = pool
        context["pool_counts"] = registration_service.pool_counts(pool)
    # Same context the fragment uses, so a live page and a filled static page
    # show the same entry (design 13.13.3).
    context.update(actions_context(request, tournament))
    return render(request, "tournaments/detail.html", context)
