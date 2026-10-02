"""Demo data only: replace every demo user's avatar with an anime illustration
from nekos.best (user approved 2026-10-03). The artist and source go into the
image title and description. Run with `manage.py shell < anime_avatars.py`."""

import json
import urllib.request
from io import BytesIO

from django.core.files.base import ContentFile
from PIL import Image as PILImage
from wagtail.images.models import Image
from wagtail.models import Collection

from accounts.models import User

UA = {"User-Agent": "sjtu-ow-demo/1.0"}
PLAN = [("waifu", 14), ("neko", 12), ("husbando", 10), ("kitsune", 4)]


def get(url, timeout=30):
    with urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=timeout) as r:
        return r.read()


pool = []
for category, amount in PLAN:
    data = json.loads(get(f"https://nekos.best/api/v2/{category}?amount={amount}"))
    pool += data["results"]
print("api results:", len(pool))

root = Collection.get_first_root_node()
collection = root.get_children().filter(name="头像").first() or root.add_child(name="头像")
old_ids = list(User.objects.exclude(avatar=None).values_list("avatar_id", flat=True))

users = list(User.objects.order_by("pk"))
done = 0
for user, item in zip(users, pool):
    raw = get(item["url"], timeout=60)
    picture = PILImage.open(BytesIO(raw))
    width, height = picture.size
    ext = item["url"].rsplit(".", 1)[-1].lower()
    image = Image(
        title=f"头像 · {user.nickname} · 画师 {item.get('artist_name') or '未知'}"[:255],
        description=(
            f"画师：{item.get('artist_name') or '未知'}（{item.get('artist_href') or ''}）"
            f"；出处：{item.get('source_url') or ''}；经 nekos.best，演示数据"
        )[:255],
        collection=collection,
        width=width,
        height=height,
        file=ContentFile(raw, name=f"anime-{user.pk}.{ext}"),
    )
    # Faces sit near the top of a portrait illustration.
    image.focal_point_x = width // 2
    image.focal_point_y = int(height * (0.28 if height > width else 0.4))
    image.focal_point_width = width // 2
    image.focal_point_height = width // 2
    image.save()
    user.avatar = image
    user.save(update_fields=["avatar"])
    done += 1
print("avatars replaced:", done)

removed = 0
for image in Image.objects.filter(pk__in=old_ids):
    image.delete()
    removed += 1
print("old avatars deleted:", removed)
