"""The three positions, and what a member shows about them in public
(design-details 3.2, 3.3; v5.2)."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timedelta

from django.utils import timezone

from accounts.ranks import format_rank

ROLE_CHOICES = [("tank", "坦克"), ("damage", "输出"), ("support", "支援")]
ROLE_LABELS = dict(ROLE_CHOICES)
ROLE_ORDER = tuple(code for code, _label in ROLE_CHOICES)
RANK_FIELDS = {role: f"rank_{role}" for role in ROLE_ORDER}
# A season resets ranks; an older one is shown greyed out (3.3 #6).
STALE_AFTER = timedelta(days=180)


def parse_roles(value) -> list[str]:
    """Known role codes from ``"support,tank"`` (or a list), in the fixed
    order tank, damage, support, each once."""
    if isinstance(value, str):
        value = value.split(",")
    wanted = {str(code).strip() for code in value or ()}
    return [role for role in ROLE_ORDER if role in wanted]


def join_roles(codes) -> str:
    return ",".join(parse_roles(codes))


@dataclass(frozen=True)
class RoleRank:
    role: str
    score: int
    updated_at: datetime | None
    stale: bool

    @property
    def role_label(self) -> str:
        return ROLE_LABELS[self.role]

    @property
    def label(self) -> str:
        return format_rank(self.score)


@dataclass
class PublicProfile:
    """What the member page and team pages print about one person."""

    roles: list[str] = field(default_factory=list)
    main_role: str = ""
    ranks: list[RoleRank] = field(default_factory=list)

    @property
    def main_rank(self) -> RoleRank | None:
        return self.ranks[0] if self.ranks else None

    @property
    def is_flex(self) -> bool:
        return len(self.roles) == len(ROLE_ORDER)

    @property
    def role_items(self) -> list[tuple[str, str, bool]]:
        """(code, label, is_main) in display order."""
        return [
            (role, ROLE_LABELS[role], role == self.main_role) for role in self.roles
        ]


def best_ranks(accounts, now=None) -> dict[str, RoleRank]:
    """Each role's highest rank over all of a person's game IDs (3.3 #1)."""
    now = now or timezone.now()
    best: dict[str, RoleRank] = {}
    for account in accounts:
        for role, name in RANK_FIELDS.items():
            score = getattr(account, name)
            if score is None:
                continue
            if role not in best or score > best[role].score:
                updated = account.ranks_updated_at
                stale = bool(updated and now - updated > STALE_AFTER)
                best[role] = RoleRank(role, score, updated, stale)
    return best


def public_profile(user, now=None) -> PublicProfile:
    """Roles as the person ordered them (main first); ranks only for those
    roles, or for every ranked role when none are set, highest first; no
    ranks at all when the person keeps them private (3.3)."""
    main = user.main_role if user.main_role in ROLE_LABELS else ""
    roles = ([main] if main else []) + [
        role for role in parse_roles(user.flex_roles) if role != main
    ]
    profile = PublicProfile(roles=roles, main_role=main)
    if not user.show_rank:
        return profile
    best = best_ranks(user.game_accounts.all(), now=now)
    if roles:
        profile.ranks = [best[role] for role in roles if role in best]
    else:
        profile.ranks = sorted(best.values(), key=lambda rank: -rank.score)
    return profile
