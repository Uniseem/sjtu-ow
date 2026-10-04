from django.urls import path

from core import styleguide, views

urlpatterns = [
    path("", views.home, name="home"),
    path("healthz", views.healthz, name="healthz"),
    path("favicon.ico", views.site_icon, {"name": "favicon.ico"}),
    path("apple-touch-icon.png", views.site_icon, {"name": "apple-touch-icon.png"}),
    path("_fragments/state/", views.state_fragment, name="state_fragment"),
    # Design 10.4 (v6.19): the link at the foot of every activity notice.
    path(
        "unsubscribe/<str:token>/",
        views.announcements_unsubscribe,
        name="announcements_unsubscribe",
    ),
    path("calendar/<str:token>.ics", views.calendar_feed, name="calendar_feed"),
    path("_styleguide/", styleguide.styleguide, name="styleguide"),
    path(
        "_styleguide/emails/",
        styleguide.styleguide_emails,
        name="styleguide_emails",
    ),
    path(
        "_styleguide/emails/<slug:key>/",
        styleguide.styleguide_email,
        name="styleguide_email",
    ),
]
