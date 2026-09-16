import pytest

from accounts.ranks import (
    TIER_DEFS,
    decode_rank,
    encode_rank,
    format_rank,
)


@pytest.mark.parametrize("tier, _label, index", TIER_DEFS)
@pytest.mark.parametrize("division", [1, 2, 3, 4, 5])
def test_rank_roundtrip_every_tier_and_division(tier, _label, index, division):
    score = encode_rank(tier, division)
    assert score == index * 5 + (5 - division)
    assert decode_rank(score) == (tier, division)
    assert format_rank(score) == f"{_label} {division}"


def test_rank_top500_and_unranked():
    assert encode_rank("top500") == 40
    assert decode_rank(40) == ("top500", None)
    assert format_rank(40) == "前 500"
    assert encode_rank(None) is None
    assert encode_rank("unranked") is None
    assert decode_rank(None) == (None, None)
    assert format_rank(None) == "未定级"


def test_rank_example_diamond_3():
    assert encode_rank("diamond", 3) == 22
    assert decode_rank(22) == ("diamond", 3)


def test_rank_rejects_unknown_values():
    with pytest.raises(ValueError):
        encode_rank("mythic", 1)
    with pytest.raises(ValueError):
        encode_rank("gold", 6)
    with pytest.raises(ValueError):
        decode_rank(41)
    with pytest.raises(ValueError):
        decode_rank(-1)
