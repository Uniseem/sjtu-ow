"""Site-wide business logic.

Email, prerender, and settings services are added in later milestones.
"""

INITIAL_GAME_MODES = (
    "快速游戏",
    "竞技（角色限定）",
    "竞技（自由职责）",
    "角斗领域",
    "自定义",
)


def ensure_game_modes():
    """Seed the five initial modes (design 12.4.2). Repeatable."""
    from core.models import GameMode

    modes = []
    for index, name in enumerate(INITIAL_GAME_MODES):
        mode, _created = GameMode.objects.get_or_create(
            name=name,
            defaults={"sort_order": index * 10},
        )
        modes.append(mode)
    return modes
