"""Public team pages that get prerendered (design 13.13.1)."""

from __future__ import annotations


def team_targets() -> dict:
    from teams.models import Team

    targets = {"/teams/": "team_index"}
    for team in Team.objects.filter(disbanded_at__isnull=True):
        targets[team.get_absolute_url()] = "team"
    return targets
