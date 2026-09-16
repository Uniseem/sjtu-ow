"""Public scrim pages that get prerendered (design 13.13.1)."""

from __future__ import annotations


def scrim_targets() -> dict:
    from scrims import services

    targets = {"/scrims/": "scrim_index"}
    for scrim in services.public_scrims():
        targets[f"/scrims/{scrim.pk}/"] = "scrim"
    return targets
