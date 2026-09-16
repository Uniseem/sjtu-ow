"""The signup box on a scrim page (design 9.2, 13.13.3).

The live page and the fragment must show the same thing, so both build
their context here.
"""

from __future__ import annotations

from django.template.loader import render_to_string

from scrims import services
from scrims.models import Role, ScrimStatus


def actions_context(request, scrim) -> dict:
    user = getattr(request, "user", None)
    signed_in = bool(getattr(user, "is_authenticated", False))
    my_signup = scrim.signups.filter(user=user).first() if signed_in else None
    accounts = list(user.game_accounts.all()) if signed_in else []
    problems = (
        services.signup_problems(scrim=scrim, user=user) if signed_in else ["请先登录"]
    )
    return {
        "scrim": scrim,
        "my_signup": my_signup,
        "game_accounts": accounts,
        "role_choices": Role.choices,
        "signup_open": scrim.signup_open(),
        "signup_problems": problems,
        "can_sign_up": not problems and bool(accounts),
        "cancelled": scrim.status == ScrimStatus.CANCELLED,
    }


def scrim_actions_slot(request, argument):
    if not argument or not argument.isdigit():
        return ""
    scrim = services.visible_scrim(int(argument))
    if scrim is None:
        return ""
    context = actions_context(request, scrim)
    context["oob"] = True
    return render_to_string("scrims/slots/actions.html", context, request=request)
