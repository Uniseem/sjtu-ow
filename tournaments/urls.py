from django.urls import path

from tournaments import registration_views, views

urlpatterns = [
    path("tournaments/", views.tournament_index, name="tournament_index"),
    path("tournaments/<id:pk>/", views.tournament_detail, name="tournament_detail"),
    path(
        "tournaments/<id:pk>/register/",
        registration_views.register,
        name="tournament_register",
    ),
    path(
        "tournaments/<id:pk>/signup/",
        registration_views.individual_signup,
        name="tournament_individual_signup",
    ),
    path(
        "tournaments/<id:pk>/signup/cancel/",
        registration_views.individual_cancel,
        name="tournament_individual_cancel",
    ),
    path(
        "registrations/<id:pk>/",
        registration_views.registration_detail,
        name="registration_detail",
    ),
    path(
        "registrations/<id:pk>/withdraw/",
        registration_views.registration_withdraw,
        name="registration_withdraw",
    ),
    path(
        "registrations/<id:pk>/leave/",
        registration_views.registration_leave,
        name="registration_leave",
    ),
    path(
        "me/registrations/",
        registration_views.me_registrations,
        name="me_registrations",
    ),
    path(
        "me/registrations/calendar/new-address/",
        registration_views.me_calendar_reset,
        name="me_calendar_reset",
    ),
]
