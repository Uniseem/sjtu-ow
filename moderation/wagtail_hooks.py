"""Admin URLs and menu for content moderation (design 5.5.4, 14)."""

from django.urls import path, reverse
from wagtail import hooks
from wagtail.admin.menu import Menu, MenuItem, SubmenuMenuItem

from moderation.admin_views import (
    can_review,
    moderation_action,
    moderation_detail,
    moderation_index,
)


@hooks.register("register_admin_urls")
def register_moderation_urls():
    return [
        path("moderation/", moderation_index, name="moderation_index"),
        path("moderation/<int:pk>/", moderation_detail, name="moderation_detail"),
        path(
            "moderation/<int:pk>/action/",
            moderation_action,
            name="moderation_action",
        ),
    ]


class ReviewerMenuItem(MenuItem):
    def is_shown(self, request):
        return can_review(request.user)


community_menu = Menu(
    register_hook_name="register_community_menu_item",
    construct_hook_name="construct_community_menu",
)


@hooks.register("register_admin_menu_item")
def register_community_menu():
    return SubmenuMenuItem(
        "社区",
        community_menu,
        icon_name="group",
        order=300,
    )


@hooks.register("register_community_menu_item")
def register_moderation_menu_item():
    return ReviewerMenuItem(
        "内容审核",
        reverse("moderation_index"),
        icon_name="view",
        order=100,
    )
