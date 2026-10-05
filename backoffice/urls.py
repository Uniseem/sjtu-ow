"""Every back-office address, mounted at /admin/ (docs/admin.md 2).

The pages that existed before v7.0 keep their names and paths (a lot of
mail, the manual and the to-do list link to them); the tournament, scrim,
team and comment lists keep their namespaces. Each view goes through
``placed``: the door, and where the page sits.
"""

from django.urls import include, path

from backoffice.nav import placed
from backoffice.views import (
    articles,
    categories,
    comments,
    events,
    home,
    images,
    letters,
    members,
    pages,
    settings,
)
from content import markdown_views
from core import activity, admin_manual, prerender_admin
from core import views as core_views
from core.fonts import admin_views as fonts
from moderation import admin_views as moderation
from moderation import avatar_admin
from scrims import admin_views as scrim_admin
from scrims import split_admin
from teams import admin_views as team_admin
from tournaments import admin_views as tournament_admin
from tournaments import review_admin, teams_admin

backoffice_patterns = [
    path("", home.home, name="home"),
    # Design 10.5 (v7.8): letters an action wrote, sent or not.
    path("letters/", letters.letters_waiting, name="letters"),
    path("letters/<uuid:batch>/", letters.letters_confirm, name="letters_confirm"),
    # 内容
    path("articles/", articles.article_list, name="articles"),
    path("articles/new/", articles.article_new, name="article_new"),
    path("articles/<id:pk>/", articles.article_edit, name="article_edit"),
    path("articles/<id:pk>/preview/", articles.article_preview, name="article_preview"),
    path(
        "articles/<id:pk>/unpublish/",
        articles.article_unpublish,
        name="article_unpublish",
    ),
    path("articles/<id:pk>/delete/", articles.article_delete, name="article_delete"),
    path("categories/", categories.category_list, name="categories"),
    path("categories/new/", categories.category_edit, name="category_new"),
    path("categories/<id:pk>/", categories.category_edit, name="category_edit"),
    path(
        "categories/<id:pk>/delete/",
        categories.category_delete,
        name="category_delete",
    ),
    path("pages/", pages.page_list, name="pages"),
    path("pages/pins/", pages.home_pins, name="home_pins"),
    path("pages/intro/", pages.index_intro, name="index_intro"),
    path("pages/<id:pk>/", pages.page_edit, name="page_edit"),
    path("pages/<id:pk>/preview/", pages.page_preview, name="page_preview"),
    path("images/", images.image_list, name="images"),
    path("images/upload/", images.image_upload, name="image_upload"),
    path("images/chooser/", images.image_chooser, name="image_chooser"),
    path(
        "images/chooser/upload/",
        images.image_chooser_upload,
        name="image_chooser_upload",
    ),
    path("images/collections/", images.collection_list, name="collections"),
    path(
        "images/collections/<id:pk>/rename/",
        images.collection_rename,
        name="collection_rename",
    ),
    path(
        "images/collections/<id:pk>/delete/",
        images.collection_delete,
        name="collection_delete",
    ),
    path("images/<id:pk>/", images.image_edit, name="image_edit"),
    path("images/<id:pk>/delete/", images.image_delete, name="image_delete"),
    # 成员
    path("users/", members.user_list, name="users"),
    path("users/<id:pk>/", members.user_edit, name="user_edit"),
    path("users/<id:pk>/active/", members.user_active, name="user_active"),
    path("users/<id:pk>/rules/", members.user_rule_add, name="user_rule_add"),
    path(
        "users/rules/<id:pk>/delete/",
        members.user_rule_delete,
        name="user_rule_delete",
    ),
    path("roles/", members.role_list, name="roles"),
    path(
        "roles/<id:pk>/restrictions/",
        members.role_restriction_add,
        name="role_restriction_add",
    ),
    path(
        "roles/restrictions/<id:pk>/delete/",
        members.role_restriction_delete,
        name="role_restriction_delete",
    ),
    path("member-groups/", members.group_list, name="member_groups"),
    path("member-groups/new/", members.group_edit, name="member_group_new"),
    path("member-groups/<id:pk>/", members.group_edit, name="member_group_edit"),
    path(
        "member-groups/<id:pk>/delete/",
        members.group_delete,
        name="member_group_delete",
    ),
    path(
        "member-groups/<id:pk>/people/",
        members.group_people,
        name="member_group_people",
    ),
    path(
        "member-groups/<id:pk>/people/add/",
        members.group_member_add,
        name="member_group_member_add",
    ),
    path(
        "member-groups/people/<id:pk>/remove/",
        members.group_member_remove,
        name="member_group_member_remove",
    ),
    path(
        "member-groups/people/<id:pk>/move/",
        members.group_member_move,
        name="member_group_member_move",
    ),
    path(
        "member-groups/people/<id:pk>/title/",
        members.group_member_title,
        name="member_group_member_title",
    ),
    # 设置
    path("settings/site/", settings.site_settings, name="site_settings"),
    path("log/", settings.action_log, name="log"),
]

tournament_patterns = [
    path("", events.tournament_list, name="index"),
    path("new/", events.tournament_add, name="add"),
    path("edit/<id:pk>/", events.tournament_edit, name="edit"),
    path("copy/<id:pk>/", events.tournament_copy, name="copy"),
    path("delete/<id:pk>/", events.tournament_delete, name="delete"),
]

scrim_patterns = [
    path("", events.scrim_list, name="index"),
    path("new/", events.scrim_add, name="add"),
    path("edit/<id:pk>/", events.scrim_edit, name="edit"),
    path("copy/<id:pk>/", events.scrim_copy, name="copy"),
    path("delete/<id:pk>/", events.scrim_delete, name="delete"),
]

team_patterns = [
    path("", members.team_list, name="index"),
    path("edit/<id:pk>/", members.team_edit, name="edit"),
]

comment_patterns = [
    path("", comments.comment_list, name="index"),
    path("<id:pk>/<str:action>/", comments.comment_action, name="action"),
]


def _at(section, tab, view):
    return placed(section, tab)(view)


urlpatterns = [
    path("", include((backoffice_patterns, "backoffice"))),
    path("tournaments/", include((tournament_patterns, "tournaments"))),
    path("scrims/", include((scrim_patterns, "scrims"))),
    path("teams/", include((team_patterns, "teams"))),
    path("comments/", include((comment_patterns, "comments"))),
    # --- the pages from before v7.0, same names and paths ---
    path("announce/<str:kind>/<id:pk>/", events.announce, name="announce"),
    path(
        "markdown/preview/",
        _at("content", "articles", markdown_views.preview),
        name="content_markdown_preview",
    ),
    path(
        "markdown/image/",
        _at("content", "articles", markdown_views.upload_image),
        name="content_markdown_image",
    ),
    # 活动
    path(
        "tournaments/<id:pk>/teams/",
        _at("events", "tournaments", teams_admin.board_view),
        name="tournament_teams_board",
    ),
    path(
        "tournaments/<id:pk>/action/<str:action>/",
        _at("events", "tournaments", tournament_admin.tournament_action),
        name="tournament_action",
    ),
    path(
        "tournaments/<id:pk>/cancel/",
        _at("events", "tournaments", tournament_admin.tournament_cancel),
        name="tournament_cancel",
    ),
    path(
        "scrims/<id:pk>/cancel/",
        _at("events", "scrims", scrim_admin.scrim_cancel),
        name="scrim_cancel",
    ),
    path(
        "scrims/<id:pk>/split/",
        _at("events", "scrims", split_admin.split_view),
        name="scrim_split",
    ),
    path(
        "scrims/<id:pk>/split/text/",
        _at("events", "scrims", split_admin.copy_view),
        name="scrim_split_text",
    ),
    path(
        "scrims/<id:pk>/<str:action>/",
        _at("events", "scrims", scrim_admin.scrim_action),
        name="scrim_action",
    ),
    # 成员
    path(
        "teams/<id:pk>/assign-captain/",
        _at("members", "teams", team_admin.admin_assign_captain),
        name="team_assign_captain",
    ),
    path(
        "teams/<id:pk>/disband/",
        _at("members", "teams", team_admin.admin_disband),
        name="team_admin_disband",
    ),
    # 审核
    path(
        "registrations/",
        _at("review", "registrations", review_admin.review_index),
        name="registration_review_index",
    ),
    path(
        "registrations/bulk-approve/",
        _at("review", "registrations", review_admin.review_bulk_approve),
        name="registration_review_bulk",
    ),
    path(
        "registrations/export.csv",
        _at("review", "registrations", review_admin.review_export),
        name="registration_review_export",
    ),
    path(
        "registrations/<id:pk>/",
        _at("review", "registrations", review_admin.review_detail),
        name="registration_review_detail",
    ),
    path(
        "registrations/<id:pk>/action/",
        _at("review", "registrations", review_admin.review_action),
        name="registration_review_action",
    ),
    path(
        "moderation/",
        _at("review", "moderation", moderation.moderation_index),
        name="moderation_index",
    ),
    path(
        "moderation/try/",
        _at("review", "moderation", moderation.moderation_try),
        name="moderation_try",
    ),
    path(
        "moderation/<id:pk>/",
        _at("review", "moderation", moderation.moderation_detail),
        name="moderation_detail",
    ),
    path(
        "moderation/<id:pk>/action/",
        _at("review", "moderation", moderation.moderation_action),
        name="moderation_action",
    ),
    path(
        "moderation/<id:pk>/ask-author/",
        _at("review", "moderation", moderation.moderation_ask_author),
        name="moderation_ask_author",
    ),
    path(
        "avatars/",
        _at("review", "avatars", avatar_admin.avatar_review),
        name="avatar_review",
    ),
    path(
        "avatars/<id:pk>/action/",
        _at("review", "avatars", avatar_admin.avatar_review_action),
        name="avatar_review_action",
    ),
    # 数据、手册
    path(
        "activity/",
        _at("data", "activity", activity.activity_view),
        name="admin_activity",
    ),
    path(
        "manual/",
        _at("manual", "manual", admin_manual.manual_view),
        name="admin_manual",
    ),
    # 设置
    path(
        "settings/core/send-test-email/",
        _at("settings", "site", core_views.send_site_test_email),
        name="core_send_test_email",
    ),
    path(
        "settings/core/try-offsite/",
        _at("settings", "site", core_views.try_offsite_backup),
        name="core_try_offsite",
    ),
    path(
        "settings/fonts/",
        _at("settings", "fonts", fonts.font_index),
        name="core_font_index",
    ),
    path(
        "settings/fonts/add/",
        _at("settings", "fonts", fonts.font_add),
        name="core_font_add",
    ),
    path(
        "settings/fonts/faces.css",
        _at("settings", "fonts", fonts.font_faces_css),
        name="core_font_faces_css",
    ),
    path(
        "settings/fonts/<id:pk>/",
        _at("settings", "fonts", fonts.font_detail),
        name="core_font_detail",
    ),
    path(
        "settings/fonts/<id:pk>/reprocess/",
        _at("settings", "fonts", fonts.font_reprocess),
        name="core_font_reprocess",
    ),
    path(
        "settings/fonts/<id:pk>/delete/",
        _at("settings", "fonts", fonts.font_delete),
        name="core_font_delete",
    ),
    path(
        "settings/fonts/weights/<id:pk>/download/",
        _at("settings", "fonts", fonts.font_face_download),
        name="core_font_face_download",
    ),
    path(
        "settings/fonts/weights/<id:pk>/delete/",
        _at("settings", "fonts", fonts.font_face_delete),
        name="core_font_face_delete",
    ),
    path(
        "settings/typography/",
        _at("settings", "typography", fonts.typography),
        name="core_typography",
    ),
    path(
        "settings/prerender/",
        _at("settings", "prerender", prerender_admin.prerender_index),
        name="core_prerender_index",
    ),
    path(
        "settings/prerender/rebuild/",
        _at("settings", "prerender", prerender_admin.prerender_rebuild),
        name="core_prerender_rebuild",
    ),
    path(
        "settings/prerender/clear/",
        _at("settings", "prerender", prerender_admin.prerender_clear),
        name="core_prerender_clear",
    ),
]
