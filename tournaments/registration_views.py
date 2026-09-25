"""Registration pages (design 8.3, 8.6; routes in 13.4)."""

from __future__ import annotations

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.http import Http404
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import (
    require_GET,
    require_http_methods,
    require_POST,
)

from teams.models import TeamMembership, TeamRole
from tournaments import registration as registration_service
from tournaments.models import (
    ACTIVE_STATUSES,
    Registration,
    RegistrationStatus,
    Tournament,
)


def _captain_teams(user):
    return [
        membership.team
        for membership in TeamMembership.objects.filter(
            user=user, role=TeamRole.CAPTAIN, team__disbanded_at__isnull=True
        ).select_related("team")
    ]


@login_required
def register(request, pk):
    tournament = get_object_or_404(Tournament, pk=pk)
    if not tournament.is_public:
        raise Http404
    teams = _captain_teams(request.user)
    if not teams:
        messages.error(request, "需要由队长为战队报名。")
        return redirect("tournament_detail", pk=tournament.pk)

    team_id = request.POST.get("team") or request.GET.get("team")
    team = next((item for item in teams if str(item.pk) == str(team_id)), None)
    if team is None:
        team = teams[0]

    existing = Registration.objects.filter(tournament=tournament, team=team).first()
    members = registration_service.team_members(team)
    problems = registration_service.precheck(
        tournament=tournament,
        team=team,
        actor=request.user,
        exclude_registration=existing,
    )

    if request.method == "POST" and request.POST.get("action") == "submit":
        selections = {
            key[len("account-") :]: value
            for key, value in request.POST.items()
            if key.startswith("account-")
        }
        try:
            registration = registration_service.submit(
                tournament=tournament,
                team=team,
                actor=request.user,
                selections=selections,
            )
        except registration_service.RegistrationError as exc:
            problems = exc.problems
        else:
            if registration.status == RegistrationStatus.APPROVED:
                messages.success(request, "报名已提交并自动通过。")
            else:
                messages.success(request, "报名已提交，等待审核。")
            return redirect("registration_detail", pk=registration.pk)

    rows = []
    for membership in members:
        user = membership.user
        rows.append(
            {
                "membership": membership,
                "user": user,
                "accounts": list(user.game_accounts.all()),
                "problems": registration_service.member_problems(
                    tournament=tournament, user=user
                )
                + [
                    problem
                    for problem in [
                        registration_service.existing_roster_conflict(
                            tournament=tournament,
                            user=user,
                            exclude_registration=existing,
                        )
                    ]
                    if problem
                ],
            }
        )

    return render(
        request,
        "tournaments/register.html",
        {
            "tournament": tournament,
            "team": team,
            "teams": teams,
            "rows": rows,
            "problems": problems,
            "existing": existing,
        },
    )


@login_required
@require_GET
def registration_detail(request, pk):
    registration = get_object_or_404(
        Registration.objects.select_related("tournament", "team"), pk=pk
    )
    if not registration_service.visible_to(registration, request.user):
        raise Http404
    from teams.services import is_captain as is_team_captain

    is_captain = is_team_captain(registration.team, request.user)
    return render(
        request,
        "tournaments/registration_detail.html",
        {
            "registration": registration,
            "members": registration.members.all(),
            "logs": registration.logs.all(),
            "is_captain": is_captain,
            "can_change": is_captain
            and registration_service.captain_can_change(registration),
            "roster_differs": registration_service.roster_differs_from_team(
                registration
            ),
            "active_statuses": ACTIVE_STATUSES,
            "resubmittable": registration.status
            in (RegistrationStatus.REJECTED, RegistrationStatus.WITHDRAWN),
        },
    )


@login_required
@require_POST
def registration_withdraw(request, pk):
    registration = get_object_or_404(Registration, pk=pk)
    try:
        registration_service.withdraw(registration=registration, actor=request.user)
    except registration_service.RegistrationError as exc:
        messages.error(request, str(exc))
    else:
        messages.success(request, "报名已撤回。")
    return redirect("registration_detail", pk=registration.pk)


@login_required
@require_GET
def me_registrations(request):
    from accounts.views import me_context

    return render(
        request,
        "me/registrations.html",
        me_context(
            request,
            "me_registrations",
            registrations=registration_service.my_registrations(request.user),
            individual_signups=registration_service.my_individual_signups(request.user),
        ),
    )


# --- individual signups (design 8.8.1) ----------------------------------------


def _public_tournament_or_404(pk):
    tournament = get_object_or_404(Tournament, pk=pk)
    if not tournament.is_public:
        raise Http404("赛事还没有发布。")
    return tournament


@login_required
@require_http_methods(["GET", "POST"])
def individual_signup(request, pk):
    from scrims.models import Role

    tournament = _public_tournament_or_404(pk)
    my_signup = tournament.individual_signups.filter(user=request.user).first()
    problems = []
    if request.method == "POST":
        roles = [role for role in request.POST.getlist("roles") if role in Role.values]
        try:
            registration_service.sign_up_individual(
                tournament=tournament,
                user=request.user,
                game_account_id=request.POST.get("game_account"),
                roles=roles,
            )
        except registration_service.RegistrationError as exc:
            problems = exc.problems
        else:
            messages.success(request, "个人报名已提交，等赛事管理员编队。")
            return redirect("tournament_detail", pk=tournament.pk)
    elif my_signup is None:
        # The pre-check, so people see what to fix before they fill the form.
        problems = registration_service.individual_problems(
            tournament=tournament, user=request.user
        )
    return render(
        request,
        "tournaments/individual_signup.html",
        {
            "tournament": tournament,
            "my_signup": my_signup,
            "problems": problems,
            "game_accounts": list(request.user.game_accounts.all()),
            "role_choices": Role.choices,
        },
    )


@login_required
@require_POST
def individual_cancel(request, pk):
    tournament = get_object_or_404(Tournament, pk=pk)
    try:
        registration_service.cancel_individual(tournament=tournament, user=request.user)
    except registration_service.RegistrationError as exc:
        messages.error(request, str(exc))
    else:
        messages.success(request, "个人报名已取消。")
    return redirect("tournament_detail", pk=tournament.pk)
