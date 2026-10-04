from django.templatetags.static import static
from django.urls import path, reverse
from django.utils.html import format_html
from wagtail import hooks
from wagtail.admin.menu import MenuItem

from core.admin_home import WelcomePanel
from core.admin_setup import SetupPanel
from core.admin_todo import TodoPanel, has_duties
from core.fonts import admin_views
from core.prerender_admin import prerender_clear, prerender_index, prerender_rebuild
from core.views import send_site_test_email, try_offsite_backup


@hooks.register("register_admin_urls")
def register_announce_url():
    from core.announce_admin import announce_view

    # Design 10.4 (v6.19): 「通知全体成员」 for a tournament or a scrim.
    return [path("announce/<str:kind>/<id:pk>/", announce_view, name="announce")]


@hooks.register("register_admin_urls")
def register_test_email_url():
    return [
        path(
            "settings/core/send-test-email/",
            send_site_test_email,
            name="core_send_test_email",
        ),
        # Design 16.7 (v6.28): 「测试对象存储」.
        path(
            "settings/core/try-offsite/",
            try_offsite_backup,
            name="core_try_offsite",
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
            "settings/fonts/<id:pk>/",
            admin_views.font_detail,
            name="core_font_detail",
        ),
        path(
            "settings/fonts/<id:pk>/reprocess/",
            admin_views.font_reprocess,
            name="core_font_reprocess",
        ),
        path(
            "settings/fonts/<id:pk>/delete/",
            admin_views.font_delete,
            name="core_font_delete",
        ),
        path(
            "settings/fonts/weights/<id:pk>/download/",
            admin_views.font_face_download,
            name="core_font_face_download",
        ),
        path(
            "settings/fonts/weights/<id:pk>/delete/",
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


@hooks.register("construct_homepage_panels")
def add_todo_panel(request, panels):
    """The dashboard (design 14.1, v6.67): the greeting with quick actions,
    「待办」 for the staff who handle queues (findings #24, round 118) and
    「上线清单」 for the owner (round 122). Wagtail's own panels are left out.
    Submitter-only users get their own panel from content.wagtail_hooks,
    which runs later and replaces the list."""
    own = [WelcomePanel()]
    if has_duties(request.user):
        own.append(TodoPanel())
    if request.user.is_superuser:
        own.append(SetupPanel())
    panels[:] = own


@hooks.register("insert_global_admin_css")
def admin_look():
    """The admin in the site's colours, type and shapes (14.1, v6.67)."""
    return format_html('<link rel="stylesheet" href="{}">', static("css/admin.css"))


@hooks.register("construct_main_menu", order=900)
def arrange_main_menu(request, menu_items):
    """In the order of the work (14.1, v6.67); before the submitters' filter
    in content.wagtail_hooks (order 1000)."""
    from core.admin_home import arrange_main_menu as arrange

    arrange(request, menu_items)


@hooks.register("construct_main_menu", order=1100)
def group_into_sections(request, menu_items):
    """The eight sections (14.1, v6.71), from whatever the two hooks above
    left this person."""
    from core.admin_sections import arrange

    arrange(request, menu_items)


@hooks.register("construct_settings_menu")
def arrange_settings_menu(request, menu_items):
    from core.admin_home import arrange_settings_menu as arrange

    arrange(request, menu_items)


@hooks.register("register_log_actions")
def register_admin_log_actions(actions):
    from core.admin_log import ACTIONS

    for action, (label, message) in ACTIONS.items():
        actions.register_action(action, label, message)


class ManualMenuItem(MenuItem):
    """「后台手册」 for every role that has a part in it (design 14.1, v6.47)."""

    def is_shown(self, request):
        from core.admin_manual import parts_for

        return bool(parts_for(request.user))


@hooks.register("register_admin_urls")
def register_manual_url():
    from core.admin_manual import manual_view

    return [path("manual/", manual_view, name="admin_manual")]


@hooks.register("register_admin_menu_item")
def register_manual_menu_item():
    return ManualMenuItem(
        "后台手册", reverse("admin_manual"), icon_name="help", order=990
    )


class ActivityMenuItem(MenuItem):
    """「活动数据」 for the officers (design 14.2, v6.53)."""

    def is_shown(self, request):
        from core.activity import can_view

        return can_view(request.user)


@hooks.register("register_admin_urls")
def register_activity_url():
    from core.activity import activity_view

    return [path("activity/", activity_view, name="admin_activity")]


@hooks.register("register_community_menu_item")
def register_activity_menu_item():
    return ActivityMenuItem(
        "活动数据", reverse("admin_activity"), icon_name="table", order=90
    )
