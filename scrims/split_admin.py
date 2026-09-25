"""The admin split page (design 9.3, 9.5, 9.6)."""

from __future__ import annotations

from django.contrib import messages
from django.http import HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse

from scrims import services, teaming
from scrims.models import ROLE_REQUIREMENTS, Role, Scrim


def breadcrumbs(scrim):
    return [
        {"url": reverse("wagtailadmin_home"), "label": "首页"},
        {"url": reverse("scrims:index"), "label": "内战"},
        {"url": "", "label": f"{scrim.title} · 分队"},
    ]


def zones_for(scrim, members):
    """Split one team's members into the drop targets the page shows.

    Role-queue formats get one zone per role, so dropping a card into 「坦克」
    is what assigns the role — there is no separate control to forget. Open
    formats get a single zone, since they have no roles at all.
    """
    if not scrim.role_queue:
        return [
            {
                "role": "",
                "label": "上场",
                "members": members,
                "capacity": scrim.team_size,
            }
        ]
    labels = dict(Role.choices)
    wanted = ROLE_REQUIREMENTS[scrim.format]
    zones = []
    for role in (Role.TANK, Role.DAMAGE, Role.SUPPORT):
        zones.append(
            {
                "role": role,
                "label": labels[role],
                "members": [row for row in members if row.assigned_role == role],
                "capacity": wanted[role],
            }
        )
    # Anyone on the team without a role still has to be visible somewhere.
    stray = [row for row in members if row.assigned_role not in wanted]
    if stray:
        zones.append({"role": "", "label": "未分位置", "members": stray, "capacity": 0})
    return zones


def page_context(request, scrim):
    order = request.GET.get("order", "created")
    signups = services.all_signups(scrim, order=order)
    rows = services.team_rows(scrim)
    bench = [row for row in signups if row.team not in ("a", "b") and row.is_selected]
    sides = [
        {
            "team": team,
            "label": label,
            "total": services.team_total(rows[team]),
            "problems": services.requirement_problems(scrim, rows[team]),
            "zones": zones_for(scrim, rows[team]),
        }
        for team, label in (("a", "A 队"), ("b", "B 队"))
    ]
    total_a = services.team_total(rows["a"])
    total_b = services.team_total(rows["b"])
    return {
        "page_title": f"{scrim.title} · 分队",
        "header_icon": "group",
        "scrim": scrim,
        "signups": signups,
        "order": order,
        "selected_count": sum(1 for row in signups if row.is_selected),
        "needed": scrim.players_needed,
        "sides": sides,
        "bench": bench,
        "team_size": scrim.team_size,
        "total_a": total_a,
        "total_b": total_b,
        "gap": abs(total_a - total_b),
        "roles": Role.choices,
        "has_teams": bool(rows["a"] or rows["b"]),
        "teams_stale": services.teams_are_stale(scrim),
        "copy_text": services.copy_text(scrim) if rows["a"] or rows["b"] else "",
        "breadcrumbs_items": breadcrumbs(scrim),
    }


def _placements_from_post(request, scrim):
    """Read the per-player team/role selects back off the form (design 9.5)."""
    placements = {}
    for signup in scrim.signups.select_related("game_account"):
        team = request.POST.get(f"team-{signup.pk}", "")
        if team not in ("a", "b"):
            continue
        role = request.POST.get(f"role-{signup.pk}", "")
        if not scrim.role_queue:
            role = ""
        elif role not in Role.values:
            role = signup.assigned_role or ""
        rating = signup.rating_for(role) if scrim.role_queue and role else None
        if rating is None:
            rating = signup.best_rating
        placements[signup.pk] = (team, role, rating)
    return placements


def split_view(request, pk):
    scrim = get_object_or_404(Scrim, pk=pk)
    if not services.can_manage(request.user):
        from django.core.exceptions import PermissionDenied

        raise PermissionDenied("需要内战管理权限。")

    if request.method == "POST":
        action = request.POST.get("action")
        if action == "select":
            services.set_selection(
                scrim=scrim, signup_ids=request.POST.getlist("signups")
            )
            messages.success(request, "已保存上场名单。")
        elif action == "generate":
            services.set_selection(
                scrim=scrim, signup_ids=request.POST.getlist("signups")
            )
            try:
                split, players = services.generate_teams(scrim)
            except teaming.NoSolution as exc:
                messages.error(request, str(exc))
            else:
                services.save_teams(
                    scrim=scrim,
                    placements=services.placements_from_split(split, players, scrim),
                )
                messages.success(
                    request,
                    f"已生成分队，总分差 {split.score[0]}，位置分差 {split.score[1]}。",
                )
        elif action == "save":
            services.save_teams(
                scrim=scrim, placements=_placements_from_post(request, scrim)
            )
            messages.success(request, "已保存分队。")
        return redirect("scrim_split", pk=scrim.pk)

    return render(request, "scrims/admin/split.html", page_context(request, scrim))


def copy_view(request, pk):
    """Plain text, so the admin can select it or fetch it from a script."""
    scrim = get_object_or_404(Scrim, pk=pk)
    if not services.can_manage(request.user):
        from django.core.exceptions import PermissionDenied

        raise PermissionDenied("需要内战管理权限。")
    return HttpResponse(
        services.copy_text(scrim), content_type="text/plain; charset=utf-8"
    )
