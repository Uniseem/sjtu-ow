from django.apps import AppConfig


class TournamentsConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "tournaments"
    verbose_name = "赛事"

    def ready(self):
        from core.prerender import register_targets
        from core.slots import register
        from tournaments.prerender_targets import tournament_targets
        from tournaments.slots import tournament_actions_slot

        register_targets(tournament_targets)
        register("tournament-actions", tournament_actions_slot)
