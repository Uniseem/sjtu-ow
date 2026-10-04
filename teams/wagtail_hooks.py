"""Team admin for superusers (design 14.2): view, edit, assign captain, disband.

No 新建 or 删除 (round 115): a team is founded by its captain on the site
and ends by disbanding, which keeps its history and registrations.
"""

from django import forms
from django.contrib import messages
from django.db.models import Q
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import path, reverse
from wagtail import hooks
from wagtail.admin.forms import WagtailAdminModelForm
from wagtail.admin.panels import FieldPanel
from wagtail.admin.ui.menus import MenuItem as ListingMenuItem
from wagtail.admin.ui.tables import BooleanColumn
from wagtail.admin.views.generic import EditView, IndexView
from wagtail.admin.viewsets.model import ModelViewSet
from wagtail.permission_policies.base import BasePermissionPolicy
from wagtail.permissions import register_permission_policy

from accounts.models import User
from accounts.roles import ROLE_CHOICES, join_roles, parse_roles
from core import admin_log
from core.converters import as_id
from teams import services
from teams.models import Team


class SuperuserOnlyPolicy(BasePermissionPolicy):
    """Team administration is a rescue tool, not an everyday one (design 14.2)."""

    def user_has_permission(self, user, action):
        if action in ("add", "delete"):
            return False
        return bool(getattr(user, "is_superuser", False))

    def users_with_any_permission(self, actions):
        return User.objects.filter(is_superuser=True)


register_permission_policy(Team, SuperuserOnlyPolicy(Team))


class TeamIndexView(IndexView):
    def get_list_more_buttons(self, instance):
        buttons = super().get_list_more_buttons(instance)
        if not instance.is_disbanded:
            buttons.append(
                ListingMenuItem(
                    "指定队长",
                    url=reverse("team_assign_captain", args=[instance.pk]),
                    icon_name="user",
                    priority=60,
                )
            )
            buttons.append(
                ListingMenuItem(
                    "解散战队",
                    url=reverse("team_admin_disband", args=[instance.pk]),
                    icon_name="bin",
                    priority=70,
                )
            )
        return buttons


class TeamAdminForm(WagtailAdminModelForm):
    """缺的位置 as three boxes, as on the captain's page (design-details 5.2)."""

    recruiting_roles = forms.MultipleChoiceField(
        label="缺的位置",
        choices=ROLE_CHOICES,
        required=False,
        widget=forms.CheckboxSelectMultiple,
        help_text="招募中时显示在战队卡和战队主页上。都不勾表示哪个位置都要。",
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if self.instance.pk:
            self.initial["recruiting_roles"] = parse_roles(
                self.instance.recruiting_roles
            )

    def clean_recruiting_roles(self) -> str:
        return join_roles(self.cleaned_data.get("recruiting_roles") or [])


Team.base_form_class = TeamAdminForm


class TeamEditView(EditView):
    def save_instance(self):
        instance = super().save_instance()
        # Same as the captain's own edit: pages and the AI review follow (7.1).
        services.on_team_changed(instance, author=self.request.user)
        return instance


class TeamViewSet(ModelViewSet):
    model = Team
    name = "teams"
    icon = "group"
    menu_label = "战队"
    add_to_admin_menu = False
    inspect_view_enabled = True
    copy_view_enabled = False
    index_view_class = TeamIndexView
    edit_view_class = TeamEditView
    list_display = [
        "name",
        BooleanColumn("is_recruiting", label="招募中", sort_key="is_recruiting"),
        "disbanded_at",
        "created_at",
    ]
    search_fields = ["name", "description"]
    panels = [
        FieldPanel("name"),
        FieldPanel("description"),
        FieldPanel("logo"),
        FieldPanel("is_recruiting"),
        FieldPanel("recruiting_roles"),
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
        order=40,
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
    # Search by nickname or email instead of listing the first 200 (round 115).
    query = request.GET.get("q", "").strip()
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
            "header_icon": "user",
            "team": team,
            "memberships": team.memberships.select_related("user"),
            "query": query,
            "candidates": candidates,
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
            admin_log.record(team, "teams.disband", request.user)
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
            "teams/<id:pk>/assign-captain/",
            admin_assign_captain,
            name="team_assign_captain",
        ),
        path("teams/<id:pk>/disband/", admin_disband, name="team_admin_disband"),
    ]
