"""The registration export's entry in the action log (design 14.4). The
tournament pages themselves are the back office's since v7.0 (docs/admin.md
4.3; backoffice.views.events, tournaments.admin_views)."""

from wagtail import hooks


@hooks.register("register_log_actions")
def register_export_log_action(actions):
    from tournaments.review_admin import EXPORT_LOG_ACTION

    actions.register_action(EXPORT_LOG_ACTION, "导出报名名单", "导出了报名名单")
