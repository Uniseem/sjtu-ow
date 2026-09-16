from django.apps import AppConfig


class ScrimsConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "scrims"
    verbose_name = "内战"

    def ready(self):
        from core.prerender import register_targets
        from core.slots import register
        from scrims.prerender_targets import scrim_targets
        from scrims.slots import scrim_actions_slot

        register_targets(scrim_targets)
        register("scrim-actions", scrim_actions_slot)
