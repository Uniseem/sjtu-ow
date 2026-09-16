"""The registration entry on a tournament page (design 8.2, 13.13.3)."""

from __future__ import annotations

from django.template.loader import render_to_string


def tournament_actions_slot(request, argument):
    from teams.models import TeamMembership, TeamRole
    from tournaments.models import Tournament

    if not argument or not argument.isdigit():
        return ""
    tournament = Tournament.objects.filter(pk=int(argument)).first()
    if tournament is None or not tournament.is_public:
        return ""
    captain_teams = []
    if getattr(request.user, "is_authenticated", False):
        captain_teams = [
            membership.team
            for membership in TeamMembership.objects.filter(
                user=request.user,
                role=TeamRole.CAPTAIN,
                team__disbanded_at__isnull=True,
            ).select_related("team")
        ]
    return render_to_string(
        "tournaments/slots/actions.html",
        {
            "oob": True,
            "tournament": tournament,
            "captain_teams": captain_teams,
            "registration_open": tournament.registration_open(),
        },
        request=request,
    )
