from django.urls import path

from integrations import api_views, views

app_name = "api"

urlpatterns = [
    path("ping", views.PingView.as_view(), name="ping"),
    # Design 11.11: superusers only.
    path("schema/", views.ApiSchemaView.as_view(), name="schema"),
    path("docs/", views.ApiDocsView.as_view(), name="docs"),
    path(
        "tournaments",
        api_views.TournamentListView.as_view(),
        name="tournament-list",
    ),
    path(
        "tournaments/external/<str:external_id>",
        api_views.TournamentUpsertView.as_view(),
        name="tournament-upsert",
    ),
    path(
        "tournaments/<int:pk>",
        api_views.TournamentDetailView.as_view(),
        name="tournament-detail",
    ),
    path(
        "tournaments/<int:pk>/roster",
        api_views.TournamentRosterView.as_view(),
        name="tournament-roster",
    ),
    path(
        "tournaments/<int:pk>/roster.csv",
        api_views.TournamentRosterCsvView.as_view(),
        name="tournament-roster-csv",
    ),
    path(
        "tournaments/<int:pk>/stats",
        api_views.TournamentStatsView.as_view(),
        name="tournament-stats",
    ),
    path(
        "registrations",
        api_views.RegistrationListView.as_view(),
        name="registration-list",
    ),
    path(
        "registrations/review-batch",
        api_views.RegistrationReviewBatchView.as_view(),
        name="registration-review-batch",
    ),
    path(
        "registrations/<int:pk>",
        api_views.RegistrationDetailView.as_view(),
        name="registration-detail",
    ),
    path(
        "registrations/<int:pk>/logs",
        api_views.RegistrationLogsView.as_view(),
        name="registration-logs",
    ),
    path(
        "registrations/<int:pk>/review",
        api_views.RegistrationReviewView.as_view(),
        name="registration-review",
    ),
]
