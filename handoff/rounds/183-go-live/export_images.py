"""Round 183: write the Wagtail image library (rows only; the files stay in
media) to a JSON file, so a fresh database can take it back.

    manage.py shell < export_images.py       (Linux; OUT names the file)

Who uploaded an image is not kept: those accounts are the demo's and go away.
"""

import json
import os
from pathlib import Path

from wagtail.images.models import Image
from wagtail.models import Collection

OUT = Path(os.environ.get("OUT", "/app/data/images-export.json"))
SKIP = {"id", "collection", "uploaded_by_user"}


def chain(collection):
    """Names from the root's child down to this collection."""
    names = [c.name for c in collection.get_ancestors(inclusive=True) if c.depth > 1]
    return names


collections = [chain(c) for c in Collection.objects.filter(depth__gt=1).order_by("path")]
images = []
for image in Image.objects.select_related("collection").order_by("pk"):
    row = {"collection": chain(image.collection)}
    for field in Image._meta.concrete_fields:
        if field.name in SKIP:
            continue
        value = getattr(image, field.attname)
        if field.name == "file":
            value = image.file.name
        elif field.name == "created_at":
            value = value.isoformat()
        row[field.name] = value
    images.append(row)

missing = [row["file"] for row in images if not Path(Image._meta.get_field("file").storage.path(row["file"])).exists()]
OUT.write_text(
    json.dumps({"collections": collections, "images": images}, ensure_ascii=False),
    encoding="utf-8",
)
print(f"exported {len(images)} images in {len(collections)} collections to {OUT}")
print(f"files missing on disk: {len(missing)}", missing[:5])
