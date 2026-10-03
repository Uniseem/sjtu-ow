"""The personalised join area on a team page (design 13.13.3)."""

from __future__ import annotations

from django.template.loader import render_to_string


def team_join_slot(request, argument):
    from teams import services
    from teams.models import Team

    if not argument or not argument.isdigit():
        return ""
    team = Team.objects.filter(pk=int(argument), disbanded_at__isnull=True).first()
    if team is None:
        return ""
    can_apply, reason = services.can_apply(team, request.user)
    return render_to_string(
        "teams/slots/join.html",
        {
            "oob": True,
            "team": team,
            "can_apply": can_apply,
            "apply_reason": reason,
            "profile_gaps": join_gaps(request.user, can_apply),
            "is_member": services.is_member(team, request.user),
            "is_captain": services.is_captain(team, request.user),
        },
        request=request,
    )


def join_gaps(user, can_apply) -> list:
    """Round 124: where to add the game ID an application needs, so the
    notice links to it instead of only saying it is missing. The live page
    and the fragment share this."""
    from teams import services

    if not can_apply and services.lacks_game_account(user):
        return [("游戏 ID", "me_game_accounts", "")]
    return []
