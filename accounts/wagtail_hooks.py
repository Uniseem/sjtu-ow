"""Wagtail's own admin under /wagtail/, for superusers (docs/admin.md 2.1).

Users, roles and feature rules are edited in the back office since v7.0;
two things are still trimmed here so the fallback admin cannot do what the
site never allows.
"""

from wagtail.admin.views import account as wagtail_account
from wagtail.admin.views.bulk_action.registry import bulk_action_registry

from accounts.models import User

# The account page's name panel asks for 名/姓 (the site uses nicknames) and
# its picture panel takes a face outside the site's own upload (design-details
# 2.3), so both are off; the email is handled by WAGTAIL_EMAIL_MANAGEMENT_ENABLED.
wagtail_account.NameEmailSettingsPanel.is_active = lambda self: False
wagtail_account.AvatarSettingsPanel.is_active = lambda self: False


# --- the user list's bulk actions (design 3.7, v6.58) -----------------------------

# Wagtail's own: 「删除」 deletes people outright (users are only ever
# anonymised, 3.8) and 「设置启用状态」 switches accounts off without the
# reason the edit page asks for or cancelling their applications (3.7).
USER_BULK_ACTIONS_OFF = ("delete", "set_active_state")


def _without_user_bulk_actions(scan):
    """The registry fills itself the first time a list page asks, after every
    app's hooks are in; drop the two from what it found."""

    def scan_then_drop():
        scan()
        for_users = bulk_action_registry.actions.get(User._meta.app_label, {})
        for action_type in USER_BULK_ACTIONS_OFF:
            for_users.get(User._meta.model_name, {}).pop(action_type, None)

    return scan_then_drop


bulk_action_registry._scan_for_bulk_actions = _without_user_bulk_actions(
    bulk_action_registry._scan_for_bulk_actions
)
