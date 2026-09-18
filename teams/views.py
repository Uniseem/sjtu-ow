"""Team pages (design 7, routes in 13.4)."""

from __future__ import annotations

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.http import Http404
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_GET, require_POST

from accounts.models import User
from content.seo import absolute_uri, build_seo
from core.ratelimit import over_limit
from teams import services
from teams.forms import ApplicationForm, RejectForm, TeamForm
from teams.images import create_logo
from teams.models import ApplicationStatus, Team, TeamApplication
from tournaments import services as tournament_services

CREATE_LIMIT = 3  # per user per day (design 附录 C)
APPLY_LIMIT = 20
DAY = 24 * 60 * 60


@require_GET
def team_index(request):
    recruiting_only = request.GET.get("recruiting") == "1"
    teams = services.open_teams(recruiting_only=recruiting_only)
    return render(
        request,
        "teams/index.html",
        {
            "teams": teams,
            "recruiting_only": recruiting_only,
            "max_members": services.max_members(),
        },
    )


@require_GET
def team_detail(request, pk):
    team = get_object_or_404(
        Team.objects.select_related("logo").prefetch_related("memberships__user"), pk=pk
    )
    memberships = team.memberships.select_related("user").order_by("role", "joined_at")
    can_apply, apply_reason = services.can_apply(team, request.user)
    return render(
        request,
        "teams/detail.html",
        {
            "team": team,
            "memberships": memberships,
            "captain": team.captain(),
            "max_members": services.max_members(),
            "is_member": services.is_member(team, request.user),
            "is_captain": services.is_captain(team, request.user),
            "can_apply": can_apply,
            "apply_reason": apply_reason,
            "entries": tournament_services.team_entries(team),
            # Design 13.14: name, description, logo.
            "seo": build_seo(
                request,
                title=team.name,
                description=team.description,
                image=team.logo,
                kind="team",
                canonical=absolute_uri(request, team.get_absolute_url()),
            ),
        },
    )


@login_required
def team_create(request):
    form = TeamForm(request.POST or None, request.FILES or None)
    if request.method == "POST":
        if over_limit(f"team_create:{request.user.pk}", CREATE_LIMIT, DAY):
            messages.error(request, "今天创建的战队太多了，明天再试。")
        elif form.is_valid():
            logo = None
            if form.cleaned_data.get("logo_file"):
                logo = create_logo(
                    form.cleaned_data["logo_file"],
                    title=f"{form.cleaned_data['name']} 队标",
                    user=request.user,
                )
            try:
                team = services.create_team(
                    user=request.user,
                    name=form.cleaned_data["name"],
                    description=form.cleaned_data.get("description", ""),
                    logo=logo,
                    is_recruiting=form.cleaned_data.get("is_recruiting", True),
                )
            except services.TeamError as exc:
                messages.error(request, str(exc))
            else:
                messages.success(request, f"战队「{team.name}」已创建。")
                return redirect("team_manage", pk=team.pk)
    return render(
        request,
        "teams/create.html",
        {"form": form, "max_captained": services.max_captained()},
    )


@login_required
def team_apply(request, pk):
    team = get_object_or_404(Team, pk=pk)
    allowed, reason = services.can_apply(team, request.user)
    form = ApplicationForm(request.POST or None)
    if request.method == "POST":
        if not allowed:
            messages.error(request, reason)
        elif over_limit(f"team_apply:{request.user.pk}", APPLY_LIMIT, DAY):
            messages.error(request, "今天的入队申请太多了，明天再试。")
        elif form.is_valid():
            try:
                services.apply_to_team(
                    team=team,
                    user=request.user,
                    roles=form.roles(),
                    message=form.cleaned_data.get("message", ""),
                )
            except services.TeamError as exc:
                messages.error(request, str(exc))
            else:
                messages.success(request, "申请已提交，等待队长审批。")
                return redirect("team_detail", pk=team.pk)
    return render(
        request,
        "teams/apply.html",
        {"team": team, "form": form, "allowed": allowed, "reason": reason},
    )


@login_required
def team_manage(request, pk):
    team = get_object_or_404(Team, pk=pk)
    if not services.is_captain(team, request.user) and not request.user.is_superuser:
        raise Http404
    form = TeamForm(request.POST or None, request.FILES or None, instance=team)
    if request.method == "POST" and request.POST.get("form") == "profile":
        if form.is_valid():
            logo = team.logo
            if form.cleaned_data.get("remove_logo"):
                logo = None
            if form.cleaned_data.get("logo_file"):
                logo = create_logo(
                    form.cleaned_data["logo_file"],
                    title=f"{form.cleaned_data['name']} 队标",
                    user=request.user,
                )
            try:
                services.update_team(
                    team=team,
                    user=request.user,
                    name=form.cleaned_data["name"],
                    description=form.cleaned_data.get("description", ""),
                    logo=logo,
                    is_recruiting=form.cleaned_data.get("is_recruiting", True),
                )
            except services.TeamError as exc:
                messages.error(request, str(exc))
            else:
                messages.success(request, "战队资料已保存。")
                return redirect("team_manage", pk=team.pk)
    return render(
        request,
        "teams/manage.html",
        {
            "team": team,
            "form": form,
            "applications": services.pending_applications(team),
            "memberships": team.memberships.select_related("user").order_by(
                "role", "joined_at"
            ),
            "max_members": services.max_members(),
            "reject_form": RejectForm(),
        },
    )


def _application(pk):
    return get_object_or_404(
        TeamApplication.objects.select_related("team", "applicant"), pk=pk
    )


@login_required
@require_POST
def application_approve(request, pk):
    application = _application(pk)
    try:
        services.approve_application(application=application, actor=request.user)
    except services.TeamError as exc:
        messages.error(request, str(exc))
    else:
        messages.success(request, f"已通过 {application.applicant.nickname} 的申请。")
    return redirect("team_manage", pk=application.team_id)


@login_required
@require_POST
def application_reject(request, pk):
    application = _application(pk)
    form = RejectForm(request.POST)
    note = form.cleaned_data.get("note", "") if form.is_valid() else ""
    try:
        services.reject_application(
            application=application, actor=request.user, note=note
        )
    except services.TeamError as exc:
        messages.error(request, str(exc))
    else:
        messages.success(request, "已拒绝这条申请。")
    return redirect("team_manage", pk=application.team_id)


@login_required
@require_POST
def application_cancel(request, pk):
    application = _application(pk)
    try:
        services.cancel_application(application=application, actor=request.user)
    except services.TeamError as exc:
        messages.error(request, str(exc))
    else:
        messages.success(request, "申请已撤回。")
    return redirect("me_teams")


@login_required
@require_POST
def team_leave(request, pk):
    team = get_object_or_404(Team, pk=pk)
    try:
        services.leave_team(team=team, user=request.user)
    except services.TeamError as exc:
        messages.error(request, str(exc))
        return redirect("team_detail", pk=team.pk)
    messages.success(request, f"已退出「{team.name}」。")
    return redirect("me_teams")


@login_required
@require_POST
def member_remove(request, pk):
    team = get_object_or_404(Team, pk=pk)
    member = get_object_or_404(User, pk=request.POST.get("user"))
    try:
        services.remove_member(team=team, actor=request.user, member_user=member)
    except services.TeamError as exc:
        messages.error(request, str(exc))
    else:
        messages.success(request, f"已移除 {member.nickname}。")
    return redirect("team_manage", pk=team.pk)


@login_required
@require_POST
def captain_transfer(request, pk):
    team = get_object_or_404(Team, pk=pk)
    member = get_object_or_404(User, pk=request.POST.get("user"))
    try:
        services.transfer_captain(team=team, actor=request.user, new_captain=member)
    except services.TeamError as exc:
        messages.error(request, str(exc))
        return redirect("team_manage", pk=team.pk)
    messages.success(request, f"已把队长转让给 {member.nickname}。")
    return redirect("team_detail", pk=team.pk)


@login_required
@require_POST
def team_disband(request, pk):
    team = get_object_or_404(Team, pk=pk)
    try:
        services.disband_team(team=team, actor=request.user)
    except services.TeamError as exc:
        messages.error(request, str(exc))
        return redirect("team_manage", pk=team.pk)
    messages.success(request, f"战队「{team.name}」已解散。")
    return redirect("me_teams")


@login_required
@require_GET
def me_teams(request):
    from accounts.views import me_context

    return render(
        request,
        "me/teams.html",
        me_context(
            request,
            "me_teams",
            teams=services.my_teams(request.user),
            applications=services.my_applications(request.user),
            pending_status=ApplicationStatus.PENDING,
        ),
    )
