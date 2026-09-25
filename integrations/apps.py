from django.apps import AppConfig


class IntegrationsConfig(AppConfig):
    """Round 067 deleted the open API and webhooks (design v1.6).

    The package stays installed because ``tournaments/migrations/0004``
    depends on ``integrations/0001``; only the migration history is left.
    """

    default_auto_field = "django.db.models.BigAutoField"
    name = "integrations"
    verbose_name = "开放 API（已删除，仅保留迁移历史）"
