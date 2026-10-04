"""Path converters (round 166)."""

from __future__ import annotations


class IdConverter:
    """A row's id in an address: at most 18 digits, so it always fits
    SQLite's 64-bit integers. Django's ``int`` takes any length; looking a
    Wagtail page up by such a number (its key is a one-to-one link, which
    Django does not range-check) fails with OverflowError, a 500 anyone could
    cause with /comments/99999999999999999999/more/. Longer numbers now simply
    match no address."""

    regex = "[0-9]{1,18}"

    def to_python(self, value: str) -> int:
        return int(value)

    def to_url(self, value) -> str:
        return str(value)
