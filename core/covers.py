"""The 默认封面 pool (design 13.2.5, v6.7).

Articles and tournaments without a cover, and every scrim banner, take a
picture from the Wagtail collection 「默认封面」: official wallpapers and
screenshots the club uploads (they never go into the repository). Same rule
as the drawn placeholders, so the same object always gets the same picture.
An empty pool falls back to those placeholders.
"""

from __future__ import annotations

from django.utils.functional import SimpleLazyObject

from core import placeholders

DEFAULT_COVER_COLLECTION = "默认封面"
# How many ways a pool picture drifts; the stylesheet has c-drift--1 … --4.
DRIFTS = 4


def load_pool() -> list:
    """The pool's images, oldest first, thumbnails fetched with them: one
    query per page however many cards use it."""
    from wagtail.images import get_image_model

    return list(
        get_image_model()
        .objects.filter(collection__name=DEFAULT_COVER_COLLECTION)
        .order_by("id")
        .prefetch_related("renditions")
    )


def lazy_pool():
    return SimpleLazyObject(load_pool)


def index(obj, size: int) -> int:
    """(ID + offset) mod size, the placeholders' rule (13.2.5)."""
    offset = placeholders.KIND_OFFSETS.get(obj._meta.label_lower, 0)
    return ((obj.pk or 0) + offset) % size


def pick(obj, pool):
    """The pool picture for this object, or None when the pool is empty."""
    images = list(pool)
    if not images:
        return None
    return images[index(obj, len(images))]
