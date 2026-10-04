"""Rescue tools for superusers (design 7.4, 14.2; docs/admin.md 4.4): hand a
team to someone when its captain is gone, or disband it. Moved out of
wagtail_hooks in v7.0."""

from __future__ import annotations

from functools import wraps

from django.contrib import messages
from django.core.exceptions import PermissionDenied
from django.db.models import Q
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse

from accounts.models import User
from core import admin_log
from core.converters import as_id
from teams import services
from teams.models import Team


def superuser_required(view):
    @wraps(view)
    def wrapper(request, *args, **kwargs):
        if not request.user.is_superuser:
            raise PermissionDenied("战队管理仅限超级管理员。")
        return view(request, *args, **kwargs)

    return wrapper


def _back(team) -> dict:
    return {"back_url": reverse("teams:edit", args=[team.pk]), "back_label": team.name}


@superuser_required
def admin_assign_captain(request, pk):
    team = get_object_or_404(Team, pk=pk)
    # Search by nickname or email instead of listing the first 200 (round 115).
    query = request.GET.get("q", "").strip()[:50]
    candidates = User.objects.filter(is_active=True).order_by("nickname")
    if query:
        candidates = candidates.filter(
            Q(nickname__icontains=query) | Q(email__icontains=query)
        )
    candidates = candidates[:50]
    if request.method == "POST":
        user = get_object_or_404(User, pk=as_id(request.POST.get("user")))
        try:
            services.assign_captain(team=team, actor=request.user, new_captain=user)
        except services.TeamError as exc:
            messages.error(request, str(exc))
        else:
            admin_log.record(
                team,
                "teams.assign_captain",
                request.user,
                captain=user.nickname,
                captain_id=user.pk,
            )
            messages.success(
                request, f"已指定 {user.nickname} 为「{team.name}」的队长。"
            )
            return redirect("teams:index")
    return render(
        request,
        "teams/admin/assign_captain.html",
        {
            "page_title": f"指定队长：{team.name}",
            "team": team,
            "memberships": team.memberships.select_related("user"),
            "query": query,
            "candidates": candidates,
            **_back(team),
        },
    )


@superuser_required
def admin_disband(request, pk):
    team = get_object_or_404(Team, pk=pk)
    if request.method == "POST":
        try:
            services.disband_team(team=team, actor=request.user)
        except services.TeamError as exc:
            messages.error(request, str(exc))
        else:
            admin_log.record(team, "teams.disband", request.user)
            messages.success(request, f"战队「{team.name}」已解散。")
        return redirect("teams:index")
    return render(
        request,
        "teams/admin/disband.html",
        {"page_title": f"解散战队：{team.name}", "team": team, **_back(team)},
    )
