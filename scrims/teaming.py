"""The team-split algorithm (design 9.4).

Role-queue formats need every player placed in a role they can actually
play, with both teams as close as possible in strength. Open formats just
balance totals.

The search is exhaustive but small: 5v5 has 126 ways to split ten players
(C(9,4) after pinning the first player to A), 6v6 has 462. For each split
we enumerate every legal role assignment per team — at most 30 for 5v5 and
90 for 6v6 — and pair the two sides up. Pairing naively would be 90x90 per
split; design 9.4 calls for deduplicating and sorting assignments by total
first, which is what :func:`_best_pairing` does.
"""

from __future__ import annotations

import bisect
import random
from dataclasses import dataclass
from itertools import combinations

from scrims.models import ROLE_REQUIREMENTS, Role

ROLE_ORDER = (Role.TANK, Role.DAMAGE, Role.SUPPORT)


class NoSolution(Exception):
    """No legal split exists; the message says why (design 9.4)."""


@dataclass(frozen=True)
class Player:
    """One selected signup, reduced to what the algorithm needs."""

    signup_id: int
    nickname: str
    battletag: str
    roles: tuple[str, ...]
    ratings: dict[str, int]  # role -> score, only for roles they can play
    best: int  # highest score on the chosen account (open formats)

    def rating(self, role) -> int:
        return self.ratings.get(role, 0)


@dataclass
class Assignment:
    """One team: who plays what, with the totals design 9.4 compares."""

    by_role: dict[str, tuple[int, ...]]  # role -> signup ids
    total: int
    role_totals: dict[str, int]


@dataclass
class Split:
    a: Assignment
    b: Assignment
    score: tuple[int, int]


def players_from(signups, scrim) -> list[Player]:
    players = []
    for signup in signups:
        ratings = {
            role: signup.rating_for(role)
            for role in signup.roles
            if signup.rating_for(role) is not None
        }
        players.append(
            Player(
                signup_id=signup.pk,
                nickname=signup.user.nickname,
                battletag=signup.game_account.battletag,
                roles=tuple(signup.roles),
                ratings=ratings,
                best=signup.best_rating or 0,
            )
        )
    return players


# --- feasibility ---------------------------------------------------------------


ROLE_LABELS = dict(Role.choices)


def check_feasible(players, scrim) -> None:
    """Explain why no split is possible, before spending time searching."""
    needed = scrim.players_needed
    if len(players) != needed:
        raise NoSolution(
            f"需要正好 {needed} 人才能分队，当前勾选了 {len(players)} 人。"
        )
    if not scrim.role_queue:
        return
    requirements = ROLE_REQUIREMENTS[scrim.format]
    for role, per_team in requirements.items():
        able = [player for player in players if role in player.roles]
        total_needed = per_team * 2
        if len(able) < total_needed:
            raise NoSolution(
                f"能打{ROLE_LABELS[role]}的玩家只有 {len(able)} 人，"
                f"{scrim.get_format_display()} 需要至少 {total_needed} 人。"
            )
    stuck = [player.nickname for player in players if not player.ratings]
    if stuck:
        raise NoSolution(
            f"这些玩家在所选游戏 ID 上没有可用的段位：{'、'.join(stuck)}。"
        )


# --- role-queue assignments ----------------------------------------------------


def _assignments(team: tuple[Player, ...], requirements) -> list[Assignment]:
    """Every legal way to fill the required roles with exactly these players."""
    results: list[Assignment] = []
    roles = [role for role in ROLE_ORDER if requirements.get(role)]

    def walk(index, remaining, chosen):
        if index == len(roles):
            if remaining:
                return
            by_role = {role: tuple(ids) for role, ids in chosen.items()}
            role_totals = {
                role: sum(lookup[pid].rating(role) for pid in ids)
                for role, ids in by_role.items()
            }
            results.append(
                Assignment(
                    by_role=by_role,
                    total=sum(role_totals.values()),
                    role_totals=role_totals,
                )
            )
            return
        role = roles[index]
        eligible = [player for player in remaining if role in player.roles]
        for picked in combinations(eligible, requirements[role]):
            still = tuple(p for p in remaining if p not in picked)
            chosen[role] = [p.signup_id for p in picked]
            walk(index + 1, still, chosen)
            del chosen[role]

    lookup = {player.signup_id: player for player in team}
    walk(0, team, {})
    return results


def _prune(assignments: list[Assignment]) -> list[Assignment]:
    """Design 9.4: dedupe and sort by total before pairing.

    Two assignments with the same total and the same per-role totals score
    identically against any opponent, so only one needs to survive.
    """
    seen = {}
    for assignment in assignments:
        key = (assignment.total, tuple(sorted(assignment.role_totals.items())))
        seen.setdefault(key, assignment)
    return sorted(seen.values(), key=lambda item: item.total)


def _score(a: Assignment, b: Assignment) -> tuple[int, int]:
    """Design 9.4: total gap first, then the sum of per-role gaps."""
    role_gap = sum(
        abs(a.role_totals.get(role, 0) - b.role_totals.get(role, 0))
        for role in a.role_totals
    )
    return (abs(a.total - b.total), role_gap)


def _best_pairing(side_a, side_b, limit=None):
    """Cheapest (a, b) pair. Both sides arrive sorted by total.

    Pairing every A with every B is 90x90 per split for 6v6, which blows the
    one-second budget. Because the score compares the total gap first and
    both sides are sorted, the closest totals to ``a.total`` are found by
    bisection and we can walk outward only while the total gap could still
    matter.

    ``limit`` is the best score found across earlier splits. A candidate
    whose total gap already exceeds ``limit[0]`` scores strictly worse than
    that, so it can neither beat nor tie the winner and the walk stops --
    which keeps ties collectable for "重新生成".
    """
    totals_b = [assignment.total for assignment in side_b]
    best = None
    best_score = None
    for a in side_a:
        position = bisect.bisect_left(totals_b, a.total)
        low, high = position - 1, position
        while low >= 0 or high < len(side_b):
            if low >= 0 and high < len(side_b):
                if a.total - totals_b[low] <= totals_b[high] - a.total:
                    candidate, low = side_b[low], low - 1
                else:
                    candidate, high = side_b[high], high + 1
            elif low >= 0:
                candidate, low = side_b[low], low - 1
            else:
                candidate, high = side_b[high], high + 1

            gap = abs(a.total - candidate.total)
            if limit is not None and gap > limit[0]:
                break
            if best_score is not None and gap > best_score[0]:
                break
            score = _score(a, candidate)
            if best_score is None or score < best_score:
                best, best_score = (a, candidate), score
        if best_score == (0, 0):
            break
    return best, best_score


def _role_queue_splits(players, requirements, best_so_far=None):
    """Yield (score, a_assignment, b_assignment) for every feasible split.

    ``best_so_far`` is a one-element list holding the best score seen, so the
    pairing search can prune against it as the scan progresses.
    """
    first, rest = players[0], players[1:]
    size = len(players) // 2
    for others in combinations(rest, size - 1):
        team_a = (first, *others)
        team_b = tuple(player for player in rest if player not in others)
        side_a = _prune(_assignments(team_a, requirements))
        if not side_a:
            continue
        side_b = _prune(_assignments(team_b, requirements))
        if not side_b:
            continue
        limit = best_so_far[0] if best_so_far else None
        pair, score = _best_pairing(side_a, side_b, limit=limit)
        if pair is None:
            continue
        if best_so_far is not None and (
            best_so_far[0] is None or score < best_so_far[0]
        ):
            best_so_far[0] = score
        yield score, pair[0], pair[1]


# --- open formats --------------------------------------------------------------


def _open_splits(players):
    first, rest = players[0], players[1:]
    size = len(players) // 2
    for others in combinations(rest, size - 1):
        team_a = (first, *others)
        team_b = tuple(player for player in rest if player not in others)
        total_a = sum(player.best for player in team_a)
        total_b = sum(player.best for player in team_b)
        a = Assignment(
            by_role={"": tuple(p.signup_id for p in team_a)},
            total=total_a,
            role_totals={},
        )
        b = Assignment(
            by_role={"": tuple(p.signup_id for p in team_b)},
            total=total_b,
            role_totals={},
        )
        yield (abs(total_a - total_b), 0), a, b


# --- entry point ---------------------------------------------------------------


def generate(players, scrim, *, rng=None) -> Split:
    """The best split, picking at random among ties (design 9.4)."""
    check_feasible(players, scrim)
    rng = rng or random

    if scrim.role_queue:
        running_best = [None]
        candidates = _role_queue_splits(
            players, ROLE_REQUIREMENTS[scrim.format], running_best
        )
    else:
        candidates = _open_splits(players)

    best_score = None
    tied: list[Split] = []
    for score, a, b in candidates:
        if best_score is None or score < best_score:
            best_score = score
            tied = [Split(a=a, b=b, score=score)]
        elif score == best_score:
            tied.append(Split(a=a, b=b, score=score))

    if not tied:
        raise NoSolution(
            "找不到合法的分队方案：每个位置都要有足够的、能打这个位置的玩家。"
        )
    return rng.choice(tied)


def ratings_used(split: Split, players, scrim) -> dict[int, int]:
    """The score each player was counted with, for ``rating_used``."""
    lookup = {player.signup_id: player for player in players}
    used = {}
    for assignment in (split.a, split.b):
        for role, ids in assignment.by_role.items():
            for signup_id in ids:
                player = lookup[signup_id]
                used[signup_id] = (
                    player.rating(role) if scrim.role_queue else player.best
                )
    return used
