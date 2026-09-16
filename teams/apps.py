from django.apps import AppConfig


class TeamsConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "teams"
    verbose_name = "战队"

    def ready(self):
        from core.prerender import register_targets
        from core.slots import register
        from teams.prerender_targets import team_targets
        from teams.slots import team_join_slot

        register_targets(team_targets)
        register("team-join", team_join_slot)
