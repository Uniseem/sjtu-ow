from django.urls import path

from scrims import views

# No app_name: the Wagtail admin viewset already owns the "scrims" namespace
# (same convention as tournaments/urls.py).
urlpatterns = [
    path("scrims/", views.scrim_index, name="scrim_index"),
    path("scrims/<id:pk>/", views.scrim_detail, name="scrim_detail"),
    path("scrims/<id:pk>/signup/", views.scrim_signup, name="scrim_signup"),
    path(
        "scrims/<id:pk>/cancel/",
        views.scrim_cancel_signup,
        name="scrim_cancel_signup",
    ),
    path("me/scrims/", views.me_scrims, name="me_scrims"),
    path(
        "_fragments/scrims/<id:pk>/actions/",
        views.scrim_actions_fragment,
        name="scrim_actions_fragment",
    ),
]
