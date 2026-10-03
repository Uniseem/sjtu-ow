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
    # Design 8.2 (v5.3): the way in depends on the tournament's mode first and
    # on who you are second. Captains sign up alone like anyone else when the
    # tournament takes individuals.
    captain_teams = []
    my_registration = None
    on_roster = None
    my_signup = None
    individual_problems = []
    if signed_in and tournament.takes_teams:
        captain_teams = captain_teams_for(user)
        if captain_teams:
            my_registration = (
                Registration.objects.filter(
                    tournament=tournament, team__in=captain_teams
                )
                .order_by("-submitted_at")
                .first()
            )
        else:
            # Entered by a captain without confirming: this is where they see it.
            on_roster = (
                Registration.objects.filter(
                    tournament=tournament,
                    members__user=user,
                    members__is_active=True,
                )
                .order_by("-submitted_at")
                .first()
            )
    if signed_in and tournament.takes_individuals:
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
        "on_roster": on_roster,
        "my_signup": my_signup,
        "individual_problems": individual_problems,
        # Round 124: the notice says what is missing and links to fill it in.
        "profile_gaps": _gaps(user) if individual_problems else [],
        # Design 8.1 (v6.32): only for the people taking part.
        "participant_contact": (
            tournament.participant_contact
            if signed_in
            and tournament.participant_contact
            and registration_service.takes_part(tournament, user)
            else ""
        ),
    }


def _gaps(user):
    from accounts.services import profile_gaps

    return profile_gaps(user)


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
