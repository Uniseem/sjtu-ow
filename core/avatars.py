"""The 默认头像 pool (design-details 2.4, v6.9).

People without a picture take one from the Wagtail collection 「默认头像」
(hero portraits the club uploads; they never go into the repository), by
ID mod size, so a person has the same face everywhere. Deactivated and
deleted accounts keep the 底图 and the initial, as does everyone when the
pool is empty. Folders under the collection count, as for 默认封面.
"""

from __future__ import annotations

from django.utils.functional import SimpleLazyObject

from core import covers

DEFAULT_AVATAR_COLLECTION = "默认头像"


def in_pool(collection_id) -> bool:
    return covers.in_pool(collection_id, DEFAULT_AVATAR_COLLECTION)


def load_pool() -> list:
    """The pool's images with their thumbnails: one look per page."""
    return covers.load_pool(DEFAULT_AVATAR_COLLECTION)


def lazy_pool():
    return SimpleLazyObject(load_pool)


def pick(person, pool):
    """The pool face for this person, or None: they have their own picture,
    the account is closed, or the pool is empty."""
    if person is None or getattr(person, "avatar_id", None):
        return None
    if not getattr(person, "is_active", False) or not person.pk:
        return None
    images = list(pool)
    if not images:
        return None
    return images[person.pk % len(images)]
