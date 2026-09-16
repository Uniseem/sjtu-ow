"""Public tournament pages that get prerendered (design 13.13.1)."""

from __future__ import annotations


def tournament_targets() -> dict:
    from tournaments.services import listed_tournaments

    targets = {"/tournaments/": "tournament_index"}
    for tournament in listed_tournaments():
        targets[tournament.get_absolute_url()] = "tournament"
    return targets
