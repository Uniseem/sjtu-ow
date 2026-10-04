"""What is left of the Wagtail admin hooks since v7.0 (docs/admin.md 2.1):
the back office is the site's own; Wagtail's admin stays under /wagtail/ for
superusers, in the site's colours, and its action log knows our actions."""

from django.templatetags.static import static
from django.utils.html import format_html
from wagtail import hooks


@hooks.register("insert_global_admin_css")
def admin_look():
    """The fallback admin in the site's colours, type and shapes (14.1, v6.67)."""
    return format_html('<link rel="stylesheet" href="{}">', static("css/admin.css"))


@hooks.register("register_log_actions")
def register_admin_log_actions(actions):
    from core.admin_log import ACTIONS

    for action, (label, message) in ACTIONS.items():
        actions.register_action(action, label, message)
