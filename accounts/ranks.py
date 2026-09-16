"""Overwatch rank score encoding (design appendix A)."""

from __future__ import annotations

TIER_DEFS: tuple[tuple[str, str, int], ...] = (
    ("bronze", "青铜", 0),
    ("silver", "白银", 1),
    ("gold", "黄金", 2),
    ("platinum", "白金", 3),
    ("diamond", "钻石", 4),
    ("master", "大师", 5),
    ("grandmaster", "宗师", 6),
    ("champion", "英杰", 7),
)

TIER_INDEX = {key: index for key, _label, index in TIER_DEFS}
TIER_LABEL = {key: label for key, label, _index in TIER_DEFS}
INDEX_TIER = {index: key for key, _label, index in TIER_DEFS}

TOP500_SCORE = 40
TOP500_TIER = "top500"
UNRANKED_LABEL = "未定级"
TOP500_LABEL = "前 500"


def encode_rank(tier: str | None, division: int | None = None) -> int | None:
    """Encode (tier, division) to a stored score. Unranked is None."""
    if not tier or tier == "unranked":
        return None
    if tier == TOP500_TIER:
        return TOP500_SCORE
    if tier not in TIER_INDEX:
        raise ValueError(f"Unknown rank tier: {tier}")
    if division not in {1, 2, 3, 4, 5}:
        raise ValueError("Rank division must be 1–5.")
    return TIER_INDEX[tier] * 5 + (5 - division)


def decode_rank(score: int | None) -> tuple[str | None, int | None]:
    """Decode a stored score to (tier, division). Unranked is (None, None)."""
    if score is None:
        return None, None
    if score == TOP500_SCORE:
        return TOP500_TIER, None
    if not isinstance(score, int) or score < 0 or score > 39:
        raise ValueError(f"Unknown rank score: {score}")
    tier_index, remainder = divmod(score, 5)
    if tier_index not in INDEX_TIER:
        raise ValueError(f"Unknown rank score: {score}")
    return INDEX_TIER[tier_index], 5 - remainder


def format_rank(score: int | None) -> str:
    """Chinese label for a stored score."""
    tier, division = decode_rank(score)
    if tier is None:
        return UNRANKED_LABEL
    if tier == TOP500_TIER:
        return TOP500_LABEL
    return f"{TIER_LABEL[tier]} {division}"


def rank_choice_value(score: int | None) -> str:
    return "" if score is None else str(score)


def parse_rank_choice(value: str) -> int | None:
    if value in (None, ""):
        return None
    return int(value)


def rank_select_choices() -> list[tuple[str, str]]:
    choices: list[tuple[str, str]] = [("", UNRANKED_LABEL), ("40", TOP500_LABEL)]
    for key, label, _index in TIER_DEFS:
        for division in (5, 4, 3, 2, 1):
            score = encode_rank(key, division)
            choices.append((str(score), f"{label} {division}"))
    return choices
