"""The admin board that forms ad-hoc teams from the pool (design 8.8.2, 14.2).

Modelled on the scrim split page (round 032): plain form POST, drag and drop
only rearranges hidden inputs, the server validates everything again.
"""

from __future__ import annotations

from django.contrib import messages
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse

from tournaments import registration as registration_service
from tournaments.models import Registration, Tournament
from tournaments.review_admin import reviewer_required

NEW_TEAM = "new"


def _breadcrumbs(tournament):
    return [
        {"url": reverse("wagtailadmin_home"), "label": "首页"},
        {"url": reverse("tournaments:index"), "label": "赛事"},
        {"url": "", "label": f"{tournament.title} · 队伍编排"},
    ]


def zone_key(registration) -> str:
    return f"r{registration.pk}"


def page_context(request, tournament):
    pool = list(
        tournament.individual_signups.select_related(
            "user", "game_account", "registration"
        ).order_by("created_at", "id")
    )
    teams = registration_service.adhoc_registrations(tournament)
    by_team = {team.pk: [] for team in teams}
    bench = []
    for entry in pool:
        entry.conflict = registration_service.pool_entry_conflict(entry)
        if entry.registration_id in by_team:
            by_team[entry.registration_id].append(entry)
        else:
            bench.append(entry)
    zones = []
    for team in teams:
        members = by_team[team.pk]
        problems = []
        if len(members) < tournament.roster_min:
            problems.append(f"人数不足：{len(members)} / 下限 {tournament.roster_min}")
        zones.append(
            {
                "key": zone_key(team),
                "registration": team,
                "name": team.team_name,
                "members": members,
                "problems": problems,
            }
        )
    move_targets = [{"key": zone["key"], "label": zone["name"]} for zone in zones]
    move_targets.append({"key": NEW_TEAM, "label": "新队伍"})
    return {
        "page_title": f"{tournament.title} · 队伍编排",
        "header_icon": "group",
        "tournament": tournament,
        "pool_total": len(pool),
        "bench": bench,
        "zones": zones,
        "move_targets": move_targets,
        "new_key": NEW_TEAM,
        "roster_min": tournament.roster_min,
        "roster_max": tournament.roster_max,
        "breadcrumbs_items": _breadcrumbs(tournament),
    }


def layout_from_post(request, tournament) -> list[dict]:
    """Turn the board's hidden inputs into the layout the service expects.

    ``team-<signup_pk>`` is ``""`` (pool), ``r<registration_pk>`` or ``new``;
    ``name-r<pk>`` / ``name-new`` carry the team names.
    """
    teams = {}
    for registration in registration_service.adhoc_registrations(tournament):
        key = zone_key(registration)
        teams[key] = {
            "registration_id": registration.pk,
            "name": request.POST.get(f"name-{key}", registration.team_name),
            "signup_ids": [],
        }
    new_team = {
        "registration_id": None,
        "name": request.POST.get(f"name-{NEW_TEAM}", ""),
        "signup_ids": [],
    }
    for entry in tournament.individual_signups.all():
        wanted = request.POST.get(f"team-{entry.pk}", "")
        if wanted == NEW_TEAM:
            new_team["signup_ids"].append(entry.pk)
        elif wanted in teams:
            teams[wanted]["signup_ids"].append(entry.pk)
    layout = list(teams.values())
    if new_team["signup_ids"]:
        layout.append(new_team)
    return layout


@reviewer_required
def board_view(request, pk):
    tournament = get_object_or_404(Tournament, pk=pk)
    if request.method == "POST":
        action = request.POST.get("action", "")
        try:
            if action == "save":
                result = registration_service.form_teams(
                    tournament=tournament,
                    actor=request.user,
                    layout=layout_from_post(request, tournament),
                )
                messages.success(
                    request,
                    f"已保存：新建 {result['created']} 支，"
                    f"调整 {result['updated']} 支，"
                    f"解散 {result['dissolved']} 支，"
                    f"移回散人池 {result['returned']} 人。",
                )
            elif action == "dissolve":
                registration = get_object_or_404(
                    Registration,
                    pk=request.POST.get("registration"),
                    tournament=tournament,
                )
                registration_service.dissolve(
                    registration=registration, actor=request.user
                )
                messages.success(request, f"「{registration.team_name}」已解散。")
            else:
                messages.error(request, "未知的操作")
        except registration_service.RegistrationError as exc:
            for problem in exc.problems:
                messages.error(request, problem)
        return redirect("tournament_teams_board", pk=tournament.pk)
    return render(
        request, "tournaments/admin/teams.html", page_context(request, tournament)
    )
