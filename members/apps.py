from django.apps import AppConfig


class MembersConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "members"
    verbose_name = "成员展示"

    def ready(self):
        from core.prerender import register_targets
        from members import signals  # noqa: F401
        from members.prerender_targets import member_targets

        register_targets(member_targets)
