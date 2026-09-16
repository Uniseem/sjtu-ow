from django.urls import path

from teams import views

urlpatterns = [
    path("teams/", views.team_index, name="team_index"),
    path("teams/new/", views.team_create, name="team_create"),
    path("teams/<int:pk>/", views.team_detail, name="team_detail"),
    path("teams/<int:pk>/apply/", views.team_apply, name="team_apply"),
    path("teams/<int:pk>/manage/", views.team_manage, name="team_manage"),
    path("teams/<int:pk>/leave/", views.team_leave, name="team_leave"),
    path("teams/<int:pk>/members/remove/", views.member_remove, name="member_remove"),
    path(
        "teams/<int:pk>/members/transfer/",
        views.captain_transfer,
        name="captain_transfer",
    ),
    path("teams/<int:pk>/disband/", views.team_disband, name="team_disband"),
    path(
        "teams/applications/<int:pk>/approve/",
        views.application_approve,
        name="application_approve",
    ),
    path(
        "teams/applications/<int:pk>/reject/",
        views.application_reject,
        name="application_reject",
    ),
    path(
        "teams/applications/<int:pk>/cancel/",
        views.application_cancel,
        name="application_cancel",
    ),
    path("me/teams/", views.me_teams, name="me_teams"),
]
