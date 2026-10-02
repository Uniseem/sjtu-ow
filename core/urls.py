from django.urls import path

from core import styleguide, views

urlpatterns = [
    path("", views.home, name="home"),
    path("healthz", views.healthz, name="healthz"),
    path("_fragments/state/", views.state_fragment, name="state_fragment"),
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
