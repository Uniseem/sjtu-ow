"""The registration entry on a tournament page (design 8.2, 13.13.3).

The live view and the fragment must show the same thing, so both build their
context here.
"""

from __future__ import annotations

from django.template.loader import render_to_string


def captain_teams_for(user):
    from teams.models import TeamMembership, TeamRole

    if not getattr(user, "is_authenticated", False):
        return []
    return [
        membership.team
        for membership in TeamMembership.objects.filter(
            user=user,
            role=TeamRole.CAPTAIN,
            team__disbanded_at__isnull=True,
        ).select_related("team")
    ]


def actions_context(request, tournament) -> dict:
    from tournaments import registration as registration_service
    from tournaments.models import IndividualSignup, Registration

    user = getattr(request, "user", None)
    signed_in = bool(getattr(user, "is_authenticated", False))
    captain_teams = captain_teams_for(user)
    my_registration = None
    if captain_teams:
        my_registration = (
            Registration.objects.filter(tournament=tournament, team__in=captain_teams)
            .order_by("-submitted_at")
            .first()
        )
    my_signup = None
    individual_problems = []
    if signed_in and not captain_teams and tournament.allow_individual_signup:
        my_signup = (
            IndividualSignup.objects.filter(tournament=tournament, user=user)
            .select_related("registration")
            .first()
        )
        if my_signup is None:
            individual_problems = registration_service.individual_problems(
                tournament=tournament, user=user
            )
    return {
        "tournament": tournament,
        "captain_teams": captain_teams,
        "registration_open": tournament.registration_open(),
        "my_registration": my_registration,
        "individual_enabled": tournament.allow_individual_signup,
        "my_signup": my_signup,
        "individual_problems": individual_problems,
    }


def tournament_actions_slot(request, argument):
    from tournaments.models import Tournament

    if not argument or not argument.isdigit():
        return ""
    tournament = Tournament.objects.filter(pk=int(argument)).first()
    if tournament is None or not tournament.is_public:
        return ""
    context = actions_context(request, tournament)
    context["oob"] = True
    return render_to_string("tournaments/slots/actions.html", context, request=request)
