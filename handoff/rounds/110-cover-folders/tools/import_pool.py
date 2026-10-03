"""Put the cropped official pictures into 默认封面, one folder each (round 110,
user approved). Run inside manage.py shell; POOL_DIR is make_pool.py's output
(pool.json and the folders).

- makes the folders under 默认封面 (each hero, 地图场景, 群像与活动, 海报)
- takes out round 109's 8 banners, which sat in 默认封面 itself
- each picture's focal point is the full width and half the height around
  the subject, so narrower banners keep the person and never zoom in
- imports in a fixed shuffled order: the pool is ordered by ID and picked by
  (ID + offset) mod size, so neighbouring articles get pictures from
  different folders instead of a run of hero banners
- skips pictures already there (same title), so it can run again; with
  RESHUFFLE=1 it first removes the folders' pictures and imports them again
"""

import hashlib
import json
import os
import random
from pathlib import Path

from django.core.files import File
from wagtail.images.models import Image

from content.services import ensure_default_cover_collection

POOL_DIR = Path(os.environ["POOL_DIR"])
pool = ensure_default_cover_collection()

old = Image.objects.filter(collection=pool, title__startswith="默认封面 · ")
print("round 109 banners removed:", old.count())
for image in old:
    image.delete()

folders = {child.name: child for child in pool.get_children()}
if os.environ.get("RESHUFFLE"):
    again = Image.objects.filter(collection__path__startswith=pool.path).exclude(collection=pool)
    print("removed to import again:", again.count())
    for image in again:
        image.delete()
items = json.loads((POOL_DIR / "pool.json").read_text(encoding="utf-8"))
random.Random(110).shuffle(items)
added = 0
for item in items:
    name = item["folder"]
    if name not in folders:
        folders[name] = pool.add_child(name=name)
    folder = folders[name]
    number = Path(item["path"]).stem
    title = f"{name} {number}"
    if Image.objects.filter(collection=folder, title=title).exists():
        continue
    width, height = item["size"]
    subject_y = item["subject"][1]
    source = item["source"] or "守望先锋官网"
    with (POOL_DIR / item["path"]).open("rb") as handle:
        Image.objects.create(
            title=title,
            description=f"{item['title']}（{source}），版权归暴雪娱乐"[:255],
            collection=folder,
            width=width,
            height=height,
            focal_point_x=width // 2,
            focal_point_y=round(height * subject_y),
            focal_point_width=width,
            focal_point_height=height // 2,
            file=File(handle, name=f"cover-{hashlib.md5(title.encode()).hexdigest()[:10]}.jpg"),
        )
    added += 1

total = Image.objects.filter(collection__path__startswith=pool.path).count()
print("added", added, "| folders", len(folders), "| pool now", total)
