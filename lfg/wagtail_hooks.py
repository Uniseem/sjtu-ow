"""Admin view of the LFG board (design 6.2: admins can close a bad post)."""

from django.contrib import messages
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import path, reverse
from wagtail import hooks
from wagtail.admin.menu import MenuItem
from wagtail.admin.ui.menus import MenuItem as ListingMenuItem
from wagtail.admin.views.generic import IndexView
from wagtail.admin.viewsets.model import ModelViewSet
from wagtail.permission_policies.base import BasePermissionPolicy
from wagtail.permissions import register_permission_policy

from accounts.models import User
from lfg import services
from lfg.models import LfgPost, LfgStatus
from moderation.admin_views import can_review, reviewer_required


class ReviewerOnlyPolicy(BasePermissionPolicy):
    """Same people who handle the review queue (design 5.5.4)."""

    def user_has_permission(self, user, action):
        return can_review(user)

    def users_with_any_permission(self, actions):
        return User.objects.filter(is_superuser=True)


register_permission_policy(LfgPost, ReviewerOnlyPolicy(LfgPost))


class LfgIndexView(IndexView):
    def get_list_more_buttons(self, instance):
        buttons = super().get_list_more_buttons(instance)
        if instance.status != LfgStatus.CLOSED:
            buttons.append(
                ListingMenuItem(
                    "关闭车帖",
                    url=reverse("lfg_admin_close", args=[instance.pk]),
                    icon_name="cross",
                    priority=60,
                )
            )
        return buttons


class LfgPostViewSet(ModelViewSet):
    model = LfgPost
    name = "lfg_posts"
    icon = "group"
    menu_label = "车帖"
    add_to_admin_menu = False
    add_view_enabled = False
    edit_view_enabled = False
    copy_view_enabled = False
    inspect_view_enabled = True
    index_view_class = LfgIndexView
    list_display = ["owner", "mode", "start_at", "status", "note"]
    search_fields = ["note"]
    # Read-only: the only admin action is closing a post (design 6.2).
    exclude_form_fields = []


@hooks.register("register_admin_viewset")
def register_lfg_viewset():
    return LfgPostViewSet()


class ReviewerMenuItem(MenuItem):
    def is_shown(self, request):
        return can_review(request.user)


@hooks.register("register_community_menu_item")
def register_lfg_menu_item():
    return ReviewerMenuItem(
        "车帖",
        reverse("lfg_posts:index"),
        icon_name="group",
        order=300,
    )


@reviewer_required
def admin_close(request, pk):
    post = get_object_or_404(LfgPost, pk=pk)
    if request.method == "POST":
        try:
            services.set_status(post=post, user=request.user, status=LfgStatus.CLOSED)
        except services.LfgError as exc:
            messages.error(request, str(exc))
        else:
            messages.success(request, "车帖已关闭。")
        return redirect("lfg_posts:index")
    return render(
        request,
        "lfg/admin/close.html",
        {
            "page_title": "关闭车帖",
            "header_icon": "cross",
            "post": post,
            "breadcrumbs_items": [
                {"url": reverse("wagtailadmin_home"), "label": "首页"},
                {"url": reverse("lfg_posts:index"), "label": "车帖"},
                {"url": "", "label": f"#{post.pk}"},
            ],
        },
    )


@hooks.register("register_admin_urls")
def register_lfg_admin_urls():
    return [
        path("lfg/<int:pk>/close/", admin_close, name="lfg_admin_close"),
    ]
