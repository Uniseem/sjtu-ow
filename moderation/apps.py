from django.apps import AppConfig


class ModerationConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "moderation"
    verbose_name = "内容审核"

    def ready(self):
        from moderation import signals  # noqa: F401
