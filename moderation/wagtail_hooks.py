"""Admin URLs and menu for content moderation (design 5.5.4, 14)."""

from django.urls import path, reverse
from wagtail import hooks
from wagtail.admin.menu import Menu, MenuItem, SubmenuMenuItem

from moderation.admin_views import (
    HANDLE_LOG_ACTION,
    can_review,
    moderation_action,
    moderation_ask_author,
    moderation_detail,
    moderation_index,
    moderation_scan,
    moderation_try,
)
from moderation.avatar_admin import avatar_review, avatar_review_action


@hooks.register("register_admin_urls")
def register_moderation_urls():
    return [
        path("moderation/", moderation_index, name="moderation_index"),
        path("moderation/scan/", moderation_scan, name="moderation_scan"),
        path("moderation/try/", moderation_try, name="moderation_try"),
        path("moderation/<int:pk>/", moderation_detail, name="moderation_detail"),
        path(
            "moderation/<int:pk>/action/",
            moderation_action,
            name="moderation_action",
        ),
        path(
            "moderation/<int:pk>/ask-author/",
            moderation_ask_author,
            name="moderation_ask_author",
        ),
        # design-details 2.3 (v6.11)
        path("avatars/", avatar_review, name="avatar_review"),
        path(
            "avatars/<int:pk>/action/",
            avatar_review_action,
            name="avatar_review_action",
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
        order=310,
    )


@hooks.register("register_community_menu_item")
def register_moderation_menu_item():
    return ReviewerMenuItem(
        "内容审核",
        reverse("moderation_index"),
        icon_name="view",
        order=50,
    )


@hooks.register("register_community_menu_item")
def register_avatar_review_menu_item():
    return ReviewerMenuItem(
        "头像审核",
        reverse("avatar_review"),
        icon_name="user",
        order=60,
    )


@hooks.register("register_log_actions")
def register_moderation_log_actions(actions):
    from moderation.services import REVISE_LOG_ACTION

    actions.register_action(HANDLE_LOG_ACTION, "处理待复核内容", "处理了待复核内容")
    actions.register_action(REVISE_LOG_ACTION, "发信要求作者修改", "发信要求作者修改")
