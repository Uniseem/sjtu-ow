"""Split a font's character set into slices (design 13.12.2 step 2).

Latin letters, digits and common punctuation go into one slice; common Chinese
characters are grouped 200 per slice; everything else is grouped into larger
slices by code point.

There is no usage-frequency table in the repository, so "common" is decided by
GB 2312 level 1 (3755 characters), which the standard itself orders by
frequency tier. This is computed from Python's ``gb2312`` codec, not from a
hand-written list.
"""

from __future__ import annotations

COMMON_SLICE_SIZE = 200
CJK_SLICE_SIZE = 600
OTHER_SLICE_SIZE = 600

# Latin, digits, punctuation, currency signs, CJK punctuation, fullwidth forms.
BASIC_RANGES = (
    (0x0020, 0x00FF),
    (0x0100, 0x024F),
    (0x2000, 0x206F),
    (0x20A0, 0x20BF),
    (0x2190, 0x21FF),
    (0x2460, 0x24FF),
    (0x25A0, 0x25FF),
    (0x3000, 0x303F),
    (0xFE30, 0xFE4F),
    (0xFF00, 0xFFEF),
)

CJK_RANGES = (
    (0x2E80, 0x2FDF),
    (0x31C0, 0x31EF),
    (0x3400, 0x4DBF),
    (0x4E00, 0x9FFF),
    (0xF900, 0xFAFF),
    (0x20000, 0x3FFFD),
)


def _in_ranges(codepoint: int, ranges) -> bool:
    return any(start <= codepoint <= end for start, end in ranges)


def is_basic(codepoint: int) -> bool:
    return _in_ranges(codepoint, BASIC_RANGES)


def is_cjk(codepoint: int) -> bool:
    return _in_ranges(codepoint, CJK_RANGES)


def is_common_hanzi(codepoint: int) -> bool:
    """GB 2312 level 1 characters (lead byte 0xB0-0xD7) are the common ones."""
    try:
        encoded = chr(codepoint).encode("gb2312")
    except (UnicodeEncodeError, UnicodeDecodeError):
        return False
    return len(encoded) == 2 and 0xB0 <= encoded[0] <= 0xD7


def _chunk(codepoints: list[int], size: int) -> list[list[int]]:
    return [codepoints[i : i + size] for i in range(0, len(codepoints), size)]


def build_slices(codepoints) -> list[list[int]]:
    """Group code points into slices, most useful first."""
    basic: list[int] = []
    common: list[int] = []
    rest_cjk: list[int] = []
    other: list[int] = []
    for codepoint in sorted(set(codepoints)):
        if is_basic(codepoint):
            basic.append(codepoint)
        elif is_cjk(codepoint):
            if is_common_hanzi(codepoint):
                common.append(codepoint)
            else:
                rest_cjk.append(codepoint)
        else:
            other.append(codepoint)

    slices: list[list[int]] = []
    if basic:
        slices.extend(_chunk(basic, CJK_SLICE_SIZE))
    slices.extend(_chunk(common, COMMON_SLICE_SIZE))
    slices.extend(_chunk(rest_cjk, CJK_SLICE_SIZE))
    slices.extend(_chunk(other, OTHER_SLICE_SIZE))
    return slices


def format_unicode_range(codepoints) -> str:
    """Render a CSS ``unicode-range`` value, collapsing consecutive runs."""
    ordered = sorted(set(codepoints))
    if not ordered:
        return ""
    parts = []
    start = previous = ordered[0]
    for codepoint in ordered[1:]:
        if codepoint == previous + 1:
            previous = codepoint
            continue
        parts.append(_format_run(start, previous))
        start = previous = codepoint
    parts.append(_format_run(start, previous))
    return ", ".join(parts)


def _format_run(start: int, end: int) -> str:
    if start == end:
        return f"U+{start:04X}"
    return f"U+{start:04X}-{end:04X}"
