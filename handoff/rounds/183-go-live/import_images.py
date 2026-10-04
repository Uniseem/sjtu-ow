"""Round 183: put the image library written by export_images.py back into a
fresh database (after migrate and init_site). The files are already in media;
only the rows and the collection tree are recreated. Renditions are made again
on demand.

    manage.py shell < import_images.py       (Linux; IN names the file)
"""

import json
import os
from datetime import datetime
from pathlib import Path

from django.db import transaction
from wagtail.images.models import Image
from wagtail.models import Collection

IN = Path(os.environ.get("IN", "/app/data/images-export.json"))
data = json.loads(IN.read_text(encoding="utf-8"))


def ensure(names):
    node = Collection.get_first_root_node()
    for name in names:
        child = node.get_children().filter(name=name).first()
        node = child or node.add_child(name=name)
    return node


with transaction.atomic():
    assert not Image.objects.exists(), "the image library is not empty; run this on a fresh database"
    nodes = {tuple(names): ensure(names) for names in data["collections"]}
    nodes[()] = Collection.get_first_root_node()
    for row in data["images"]:
        row = dict(row)
        collection = nodes[tuple(row.pop("collection"))]
        row["created_at"] = datetime.fromisoformat(row["created_at"])
        image = Image(collection=collection, **row)
        image.save()
        # auto_now_add ignores the value given on create; put it back.
        Image.objects.filter(pk=image.pk).update(created_at=row["created_at"])

print(f"imported {Image.objects.count()} images; collections now {Collection.objects.count() - 1}")
