from django.apps import AppConfig


class ContentConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "content"
    verbose_name = "内容"

    def ready(self):
        from content import signals  # noqa: F401
        from content.prerender_targets import content_targets
        from core.prerender import register_targets

        register_targets(content_targets)
