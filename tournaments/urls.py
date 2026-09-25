from django.urls import path

from tournaments import registration_views, views

urlpatterns = [
    path("tournaments/", views.tournament_index, name="tournament_index"),
    path("tournaments/<int:pk>/", views.tournament_detail, name="tournament_detail"),
    path(
        "tournaments/<int:pk>/register/",
        registration_views.register,
        name="tournament_register",
    ),
    path(
        "tournaments/<int:pk>/signup/",
        registration_views.individual_signup,
        name="tournament_individual_signup",
    ),
    path(
        "tournaments/<int:pk>/signup/cancel/",
        registration_views.individual_cancel,
        name="tournament_individual_cancel",
    ),
    path(
        "registrations/<int:pk>/",
        registration_views.registration_detail,
        name="registration_detail",
    ),
    path(
        "registrations/<int:pk>/withdraw/",
        registration_views.registration_withdraw,
        name="registration_withdraw",
    ),
    path(
        "me/registrations/",
        registration_views.me_registrations,
        name="me_registrations",
    ),
]
