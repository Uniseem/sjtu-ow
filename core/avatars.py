"""The 默认头像 pool (design-details 2.4, v6.9).

People without a picture take one from the Wagtail collection 「默认头像」
(hero portraits the club uploads; they never go into the repository), by
ID mod size, so a person has the same face everywhere. Deactivated and
deleted accounts keep the 底图 and the initial, as does everyone when the
pool is empty. Folders under the collection count, as for 默认封面; the
folders 坦克, 输出 and 支援 hold the heroes of each position, and a person
takes a face from the one for their main position (v6.10).
"""

from __future__ import annotations

from django.utils.functional import SimpleLazyObject

from accounts.roles import ROLE_CHOICES, parse_roles
from core import covers

DEFAULT_AVATAR_COLLECTION = "默认头像"
# Folder name -> position code: the folders are named as the positions are.
ROLE_BY_FOLDER = {label: code for code, label in ROLE_CHOICES}


def in_pool(collection_id) -> bool:
    return covers.in_pool(collection_id, DEFAULT_AVATAR_COLLECTION)


def load_pool() -> list:
    """The pool's images with their thumbnails, oldest first, each marked
    with the position of the top folder it sits in (``face_role``: tank,
    damage, support, or "" outside those folders). A few looks per page,
    however many faces it shows."""
    from wagtail.images import get_image_model

    root = covers.pool_root(DEFAULT_AVATAR_COLLECTION)
    if root is None:
        return []
    folders = {
        child.path: ROLE_BY_FOLDER.get(child.name, "") for child in root.get_children()
    }
    images = list(
        get_image_model()
        .objects.filter(collection__path__startswith=root.path)
        .select_related("collection")
        .order_by("id")
        .prefetch_related("renditions")
    )
    top = len(root.path) + root.steplen  # the path of the folder under the pool
    for image in images:
        image.face_role = folders.get(image.collection.path[:top], "")
    return images


def lazy_pool():
    return SimpleLazyObject(load_pool)


def position(person) -> str:
    """The position a default face follows: the main one, or else the first
    listed under 也能打 (tank, damage, support order), the one position the
    member list's small card shows; "" when none is set."""
    main = getattr(person, "main_role", "")
    if main:
        return main
    others = parse_roles(getattr(person, "flex_roles", ""))
    return others[0] if others else ""


def pick(person, pool):
    """The pool face for this person, or None: they have their own picture,
    the account is closed, or the pool is empty. Someone with a main
    position (see position()) takes one of that position's heroes; without
    one, or with that folder empty, any face (v6.10)."""
    if person is None or getattr(person, "avatar_id", None):
        return None
    if not getattr(person, "is_active", False) or not person.pk:
        return None
    images = list(pool)
    if not images:
        return None
    role = position(person)
    same = [image for image in images if role and image.face_role == role]
    choices = same or images
    return choices[person.pk % len(choices)]
