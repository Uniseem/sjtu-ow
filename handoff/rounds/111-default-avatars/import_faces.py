"""Put the 53 official hero portraits into 默认头像 (round 111, user asked
for a default face pool). Run inside manage.py shell; FACE_DIR holds
<slug>.png and names.json ({slug: hero name}). Skips faces already there."""

import json
import os
from pathlib import Path

from django.core.files import File
from wagtail.images.models import Image

from content.services import ensure_default_avatar_collection

FACE_DIR = Path(os.environ["FACE_DIR"])
names = json.loads((FACE_DIR / "names.json").read_text(encoding="utf-8"))
pool = ensure_default_avatar_collection()
added = 0
for slug in sorted(names):
    title = f"默认头像 · {names[slug]}"
    if Image.objects.filter(collection=pool, title=title).exists():
        continue
    with (FACE_DIR / f"{slug}.png").open("rb") as handle:
        Image.objects.create(
            title=title,
            description="守望先锋官网英雄列表页的英雄头像（overwatch.blizzard.com/heroes/），版权归暴雪娱乐",
            collection=pool,
            width=256,
            height=256,
            file=File(handle, name=f"face-{slug}.png"),
        )
    added += 1
print("added", added, "| pool now", Image.objects.filter(collection__path__startswith=pool.path).count())
