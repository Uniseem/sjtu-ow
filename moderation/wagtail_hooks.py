"""The moderation entries in the action log (design 14.4). The pages are the
back office's since v7.0 (docs/admin.md 4.5)."""

from wagtail import hooks

from moderation.admin_views import HANDLE_LOG_ACTION


@hooks.register("register_log_actions")
def register_moderation_log_actions(actions):
    from moderation.services import REVISE_LOG_ACTION

    actions.register_action(HANDLE_LOG_ACTION, "处理待复核内容", "处理了待复核内容")
    actions.register_action(REVISE_LOG_ACTION, "发信要求作者修改", "发信要求作者修改")
