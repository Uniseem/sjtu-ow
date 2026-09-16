from django.urls import path, reverse
from wagtail import hooks
from wagtail.admin.menu import MenuItem
from wagtail.snippets.models import register_snippet
from wagtail.snippets.views.snippets import SnippetViewSet

from core.fonts import admin_views
from core.models import GameMode
from core.prerender_admin import prerender_clear, prerender_index, prerender_rebuild
from core.views import send_site_test_email


@hooks.register("register_admin_urls")
def register_test_email_url():
    return [
        path(
            "settings/core/send-test-email/",
            send_site_test_email,
            name="core_send_test_email",
        ),
    ]


@hooks.register("register_admin_urls")
def register_font_urls():
    return [
        path("settings/fonts/", admin_views.font_index, name="core_font_index"),
        path("settings/fonts/add/", admin_views.font_add, name="core_font_add"),
        path(
            "settings/fonts/faces.css",
            admin_views.font_faces_css,
            name="core_font_faces_css",
        ),
        path(
            "settings/fonts/<int:pk>/",
            admin_views.font_detail,
            name="core_font_detail",
        ),
        path(
            "settings/fonts/<int:pk>/reprocess/",
            admin_views.font_reprocess,
            name="core_font_reprocess",
        ),
        path(
            "settings/fonts/<int:pk>/delete/",
            admin_views.font_delete,
            name="core_font_delete",
        ),
        path(
            "settings/fonts/weights/<int:pk>/download/",
            admin_views.font_face_download,
            name="core_font_face_download",
        ),
        path(
            "settings/fonts/weights/<int:pk>/delete/",
            admin_views.font_face_delete,
            name="core_font_face_delete",
        ),
        path(
            "settings/typography/",
            admin_views.typography,
            name="core_typography",
        ),
    ]


class SuperuserMenuItem(MenuItem):
    """Font and typography settings are superuser-only (design 13.12)."""

    def is_shown(self, request):
        return bool(getattr(request.user, "is_superuser", False))


@hooks.register("register_admin_urls")
def register_prerender_urls():
    return [
        path(
            "settings/prerender/",
            prerender_index,
            name="core_prerender_index",
        ),
        path(
            "settings/prerender/rebuild/",
            prerender_rebuild,
            name="core_prerender_rebuild",
        ),
        path(
            "settings/prerender/clear/",
            prerender_clear,
            name="core_prerender_clear",
        ),
    ]


@hooks.register("register_settings_menu_item")
def register_prerender_menu_item():
    return SuperuserMenuItem(
        "静态页面",
        reverse("core_prerender_index"),
        icon_name="doc-empty",
        order=820,
    )


@hooks.register("register_settings_menu_item")
def register_font_menu_item():
    return SuperuserMenuItem(
        "字体库",
        reverse("core_font_index"),
        icon_name="doc-full",
        order=800,
    )


@hooks.register("register_settings_menu_item")
def register_typography_menu_item():
    return SuperuserMenuItem(
        "排版设置",
        reverse("core_typography"),
        icon_name="edit",
        order=810,
    )


class GameModeViewSet(SnippetViewSet):
    """Game modes are managed by superusers and content editors (design 14.2)."""

    model = GameMode
    icon = "tasks"
    menu_label = "游戏模式"
    menu_name = "game_modes"
    menu_order = 260
    add_to_admin_menu = True
    list_display = ["name", "sort_order", "is_active"]
    ordering = ["sort_order", "name"]
    copy_view_enabled = False


register_snippet(GameModeViewSet)
