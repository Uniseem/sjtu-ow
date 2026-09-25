"""Template filters for the design system's fixed formats (design 13.2.4).

Dates, times, weekdays, numbering and slot meters are formatted here once so
every page prints them the same way.
"""

from __future__ import annotations

from datetime import date, datetime

from django import template
from django.utils import timezone

register = template.Library()

WEEKDAYS = "一二三四五六日"
SLOT_CELL_LIMIT = 24


def _local(value):
    if isinstance(value, datetime):
        if timezone.is_aware(value):
            return timezone.localtime(value)
        return value
    return value


@register.filter
def ow_date(value) -> str:
    """``2026.09.28``."""
    if not isinstance(value, (date, datetime)):
        return ""
    return _local(value).strftime("%Y.%m.%d")


@register.filter
def ow_md(value) -> str:
    """``09.28`` — for lists that stay within one year."""
    if not isinstance(value, (date, datetime)):
        return ""
    return _local(value).strftime("%m.%d")


@register.filter
def ow_time(value) -> str:
    """``19:30``, 24-hour clock."""
    if not isinstance(value, datetime):
        return ""
    return _local(value).strftime("%H:%M")


@register.filter
def ow_weekday(value) -> str:
    """``周五``."""
    if not isinstance(value, (date, datetime)):
        return ""
    return "周" + WEEKDAYS[_local(value).weekday()]


@register.filter
def ow_index(value) -> str:
    """Two-digit numbering: ``01``, ``02`` … ``10``."""
    try:
        return f"{int(value):02d}"
    except (TypeError, ValueError):
        return ""


@register.filter
def initial(value) -> str:
    """The first character of a name, for square avatars."""
    text = str(value or "").strip()
    return text[:1].upper() if text else "?"


@register.filter
def slot_cells(taken, capacity) -> list[str]:
    """Cells for the slot meter (13.2.6): ``on``, ``off``, then ``over``.

    Returns an empty list past SLOT_CELL_LIMIT; templates then draw the bar.
    """
    try:
        taken = max(int(taken), 0)
        capacity = max(int(capacity), 0)
    except (TypeError, ValueError):
        return []
    if max(taken, capacity) > SLOT_CELL_LIMIT:
        return []
    cells = ["on"] * min(taken, capacity)
    cells += ["off"] * max(capacity - taken, 0)
    cells += ["over"] * max(taken - capacity, 0)
    return cells


@register.filter
def percent_of(taken, capacity) -> int:
    """Whole percent for the slot bar, capped at 100."""
    try:
        taken = int(taken)
        capacity = int(capacity)
    except (TypeError, ValueError):
        return 0
    if capacity <= 0:
        return 0
    return max(0, min(100, round(taken * 100 / capacity)))


@register.filter
def rank_parts(label) -> tuple[str, str]:
    """``"钻石 3"`` → (``"钻石"``, ``"3"``); ``"前 500"`` → (``"前"``, ``"500"``)."""
    text = str(label or "").strip()
    name, _, number = text.partition(" ")
    return name, number
