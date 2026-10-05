"""How much a page's pictures weigh, and when they load (design 13.10, v6.5,
round 107). The demo's PNG avatars made one members page 4.2 MB."""

import re
from io import BytesIO
from pathlib import Path

import pytest
from django.conf import settings
from django.core.files.base import ContentFile
from PIL import Image as PILImage

# Pictures in the first screen load at once; lazy would only delay them.
FIRST_SCREEN = (
    "c-stage__img",
    "c-cover__img",
    "c-feature__img",
    "fill-288x288",
    # A letter's head (design 10.3, v7.4): inside the message, read by mail
    # clients that ignore loading=, and the first thing in it anyway.
    'src="cid:ow-',
)
SKIP = {".venv", "node_modules", "prerendered", "staticfiles", "handoff", "media"}


def _image(fmt, *, transparent=False):
    from wagtail.images.models import Image
    from wagtail.models import Collection

    collection = Collection.get_first_root_node() or Collection.add_root(name="Root")
    picture = PILImage.new("RGBA" if transparent else "RGB", (64, 64), (200, 80, 40))
    if transparent:
        picture.putpixel((0, 0), (0, 0, 0, 0))
    buffer = BytesIO()
    picture.save(buffer, fmt)
    name = {"PNG": "upload.png", "JPEG": "upload.jpg"}[fmt]
    return Image.objects.create(
        title=name,
        width=64,
        height=64,
        collection=collection,
        file=ContentFile(buffer.getvalue(), name=name),
    )


def _format(rendition):
    with rendition.file.open("rb") as handle:
        return PILImage.open(handle).format


@pytest.mark.django_db
@pytest.mark.parametrize("fmt", ["PNG", "JPEG"])
def test_thumbnails_are_webp_whatever_was_uploaded(fmt):
    rendition = _image(fmt).get_rendition("fill-88x88")
    assert rendition.url.endswith(".webp")
    assert _format(rendition) == "WEBP"
    assert settings.WAGTAILIMAGES_WEBP_QUALITY == 80


@pytest.mark.django_db
def test_a_transparent_logo_stays_transparent():
    """Uploaded team logos may be cut out; the 底图 shows through them."""
    rendition = _image("PNG", transparent=True).get_rendition("original")
    with rendition.file.open("rb") as handle:
        picture = PILImage.open(handle)
        picture.load()
        assert picture.mode == "RGBA"
        assert picture.getpixel((0, 0))[3] == 0


@pytest.mark.django_db
def test_share_images_stay_jpeg():
    """Link previews in chat apps do not all read WebP."""
    from content.seo import image_absolute_url

    url = image_absolute_url(None, _image("PNG"))
    assert url.endswith(".jpg")


def _templates():
    root = Path(settings.BASE_DIR)
    for path in root.rglob("*.html"):
        if SKIP & set(path.relative_to(root).parts):
            continue
        yield path


def test_pictures_below_the_first_screen_load_lazily():
    """Round 107: the pictures inside article bodies loaded at once."""
    eager = []
    for path in _templates():
        text = path.read_text(encoding="utf-8")
        for tag in re.findall(r"<img\b[^>]*>|\{% image [^%]*%\}", text):
            if 'loading="lazy"' in tag or any(mark in tag for mark in FIRST_SCREEN):
                continue
            eager.append(f"{path.as_posix()}: {tag[:80]}")
    assert eager == []


def test_first_screen_pictures_are_not_lazy():
    """Lazy loading would only make the banner and the cover arrive late."""
    lazy = []
    for path in _templates():
        text = path.read_text(encoding="utf-8")
        for tag in re.findall(r"<img\b[^>]*>|\{% image [^%]*%\}", text):
            if 'loading="lazy"' in tag and any(mark in tag for mark in FIRST_SCREEN):
                lazy.append(f"{path.as_posix()}: {tag[:80]}")
    assert lazy == []
