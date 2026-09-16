"""Team admin for superusers (design 14.2): view, edit, assign captain, disband."""

from django.contrib import messages
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import path, reverse
from wagtail import hooks
from wagtail.admin.panels import FieldPanel
from wagtail.admin.ui.menus import MenuItem as ListingMenuItem
from wagtail.admin.views.generic import IndexView
from wagtail.admin.viewsets.model import ModelViewSet
from wagtail.permission_policies.base import BasePermissionPolicy
from wagtail.permissions import register_permission_policy

from accounts.models import User
from teams import services
from teams.models import Team


class SuperuserOnlyPolicy(BasePermissionPolicy):
    """Team administration is a rescue tool, not an everyday one (design 14.2)."""

    def user_has_permission(self, user, action):
        return bool(getattr(user, "is_superuser", False))

    def users_with_any_permission(self, actions):
        return User.objects.filter(is_superuser=True)


register_permission_policy(Team, SuperuserOnlyPolicy(Team))


class TeamIndexView(IndexView):
    def get_list_more_buttons(self, instance):
        buttons = super().get_list_more_buttons(instance)
        buttons.append(
            ListingMenuItem(
                "指定队长",
                url=reverse("team_assign_captain", args=[instance.pk]),
                icon_name="user",
                priority=60,
            )
        )
        if not instance.is_disbanded:
            buttons.append(
                ListingMenuItem(
                    "解散战队",
                    url=reverse("team_admin_disband", args=[instance.pk]),
                    icon_name="bin",
                    priority=70,
                )
            )
        return buttons


class TeamViewSet(ModelViewSet):
    model = Team
    name = "teams"
    icon = "group"
    menu_label = "战队"
    add_to_admin_menu = False
    inspect_view_enabled = True
    copy_view_enabled = False
    index_view_class = TeamIndexView
    list_display = ["name", "is_recruiting", "disbanded_at", "created_at"]
    search_fields = ["name", "description"]
    panels = [
        FieldPanel("name"),
        FieldPanel("description"),
        FieldPanel("logo"),
        FieldPanel("is_recruiting"),
    ]


@hooks.register("register_admin_viewset")
def register_team_viewset():
    return TeamViewSet()


@hooks.register("register_community_menu_item")
def register_team_menu_item():
    from wagtail.admin.menu import MenuItem

    class SuperuserMenuItem(MenuItem):
        def is_shown(self, request):
            return bool(getattr(request.user, "is_superuser", False))

    return SuperuserMenuItem(
        "战队",
        reverse("teams:index"),
        icon_name="group",
        order=200,
    )


def superuser_required(view):
    from functools import wraps

    from django.core.exceptions import PermissionDenied

    @wraps(view)
    def wrapper(request, *args, **kwargs):
        if not request.user.is_superuser:
            raise PermissionDenied("战队管理仅限超级管理员。")
        return view(request, *args, **kwargs)

    return wrapper


@superuser_required
def admin_assign_captain(request, pk):
    """Rescue path: hand a team to someone when its captain is gone (7.4)."""
    team = get_object_or_404(Team, pk=pk)
    if request.method == "POST":
        user = get_object_or_404(User, pk=request.POST.get("user"))
        try:
            services.assign_captain(team=team, actor=request.user, new_captain=user)
        except services.TeamError as exc:
            messages.error(request, str(exc))
        else:
            messages.success(
                request, f"已指定 {user.nickname} 为「{team.name}」的队长。"
            )
            return redirect("teams:index")
    return render(
        request,
        "teams/admin/assign_captain.html",
        {
            "page_title": f"指定队长：{team.name}",
            "header_icon": "user",
            "team": team,
            "memberships": team.memberships.select_related("user"),
            "candidates": User.objects.filter(is_active=True).order_by("nickname")[
                :200
            ],
            "breadcrumbs_items": [
                {"url": reverse("wagtailadmin_home"), "label": "首页"},
                {"url": reverse("teams:index"), "label": "战队"},
                {"url": "", "label": team.name},
            ],
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
            messages.success(request, f"战队「{team.name}」已解散。")
        return redirect("teams:index")
    return render(
        request,
        "teams/admin/disband.html",
        {
            "page_title": f"解散战队：{team.name}",
            "header_icon": "bin",
            "team": team,
            "breadcrumbs_items": [
                {"url": reverse("wagtailadmin_home"), "label": "首页"},
                {"url": reverse("teams:index"), "label": "战队"},
                {"url": "", "label": team.name},
            ],
        },
    )


@hooks.register("register_admin_urls")
def register_team_admin_urls():
    return [
        path(
            "teams/<int:pk>/assign-captain/",
            admin_assign_captain,
            name="team_assign_captain",
        ),
        path("teams/<int:pk>/disband/", admin_disband, name="team_admin_disband"),
    ]
