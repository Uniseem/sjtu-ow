"""Path converters (round 166) and ids from forms (round 167)."""

from __future__ import annotations

import re


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


def as_id(value) -> int | None:
    """An id taken from a form or a query string, or None when it is not one
    (round 167): the same rule as <id:…> in addresses. Handing "abc" to a
    primary-key lookup raises ValueError, and twenty digits through a foreign
    key raise OverflowError; both were 500s."""
    text = str(value if value is not None else "").strip()
    if not re.fullmatch(IdConverter.regex, text):
        return None
    return int(text)
