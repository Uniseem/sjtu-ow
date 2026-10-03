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


def pool_root(name: str = DEFAULT_COVER_COLLECTION):
    """The 默认封面 collection itself (the top-most one of that name); the
    默认头像 pool (core.avatars) is looked up the same way."""
    from wagtail.models import Collection

    return Collection.objects.filter(name=name).order_by("depth", "path").first()


def in_pool(collection_id, name: str = DEFAULT_COVER_COLLECTION) -> bool:
    """Whether a collection is 默认封面 or one of its folders (v6.8)."""
    from wagtail.models import Collection

    root = pool_root(name)
    return bool(collection_id and root) and (
        Collection.objects.filter(pk=collection_id, path__startswith=root.path).exists()
    )


def load_pool(name: str = DEFAULT_COVER_COLLECTION) -> list:
    """The pool's images, the folders under it included (one per hero, maps,
    groups, posters; v6.8), oldest first, thumbnails fetched with them: the
    same few queries per page however many cards use it."""
    from wagtail.images import get_image_model

    root = pool_root(name)
    if root is None:
        return []
    return list(
        get_image_model()
        .objects.filter(collection__path__startswith=root.path)
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
