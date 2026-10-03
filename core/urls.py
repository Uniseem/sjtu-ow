from django.urls import path

from core import styleguide, views

urlpatterns = [
    path("", views.home, name="home"),
    path("healthz", views.healthz, name="healthz"),
    path("_fragments/state/", views.state_fragment, name="state_fragment"),
    # Design 10.4 (v6.19): the link at the foot of every activity notice.
    path(
        "unsubscribe/<str:token>/",
        views.announcements_unsubscribe,
        name="announcements_unsubscribe",
    ),
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
