from django.urls import path
from wagtail import hooks

from core.views import send_site_test_email


@hooks.register("register_admin_urls")
def register_test_email_url():
    return [
        path(
            "settings/core/send-test-email/",
            send_site_test_email,
            name="core_send_test_email",
        ),
    ]
