"""Move the 53 hero faces in 默认头像 into 坦克 / 输出 / 支援 (round 113,
design-details 2.4 v6.10). Run inside manage.py shell; FACE_DIR holds
names.json ({slug: hero name}) and roles.json ({slug: tank|damage|support},
from the official heroes page). Can run again."""

import json
import os
from collections import Counter
from pathlib import Path

from wagtail.images.models import Image

from accounts.roles import ROLE_LABELS
from content.services import ensure_default_avatar_collection

FACE_DIR = Path(os.environ["FACE_DIR"])
names = json.loads((FACE_DIR / "names.json").read_text(encoding="utf-8"))
roles = json.loads((FACE_DIR / "roles.json").read_text(encoding="utf-8"))
pool = ensure_default_avatar_collection()
folders = {child.name: child for child in pool.get_children()}
moved = Counter()
for slug, name in names.items():
    label = ROLE_LABELS[roles[slug]]
    if label not in folders:
        folders[label] = pool.add_child(name=label)
    for image in Image.objects.filter(collection__path__startswith=pool.path, title=f"默认头像 · {name}"):
        if image.collection_id != folders[label].pk:
            image.collection = folders[label]
            image.save(update_fields=["collection"])
        moved[label] += 1
left = Image.objects.filter(collection=pool).count()
print("in folders:", dict(moved), "| left loose:", left)
