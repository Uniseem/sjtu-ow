from django.apps import AppConfig


class LfgConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "lfg"
    verbose_name = "组队大厅"

    def ready(self):
        import lfg.signals  # noqa: F401
        from core.prerender import register_targets
        from core.slots import register
        from lfg.prerender_targets import lfg_targets
        from lfg.slots import home_lfg_slot

        register_targets(lfg_targets)
        register("home-lfg", home_lfg_slot)
