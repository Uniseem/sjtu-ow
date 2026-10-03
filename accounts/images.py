"""Turn an uploaded picture into a face (design-details 2.3, v6.11).

The upload is opened, turned the way the camera held it, cut to the middle
square, shrunk to at most 512 pixels and saved again as WebP. Nothing the
camera wrote into the file (place, device, time) survives, and the reviewer
sees exactly the picture that would be shown.
"""

from __future__ import annotations

import secrets
from io import BytesIO

from django.core.files.base import ContentFile
from PIL import Image as PILImage
from PIL import ImageOps

AVATAR_MAX_BYTES = 5 * 1024 * 1024
AVATAR_TYPES = {"image/jpeg", "image/png", "image/webp"}
AVATAR_EXTENSIONS = (".jpg", ".jpeg", ".png", ".webp")
AVATAR_FORMATS = {"JPEG", "PNG", "WEBP"}
AVATAR_MIN_SIDE = 128
AVATAR_MAX_PIXELS = 40_000_000  # far below Pillow's bomb limit, still any photo
AVATAR_SIDE = 512


class AvatarError(ValueError):
    """The upload is not a picture we can use; the message is for the person."""


def square_face(uploaded) -> ContentFile:
    """The picture as a square WebP of at most AVATAR_SIDE pixels."""
    uploaded.seek(0)
    try:
        picture = PILImage.open(uploaded)
        if picture.format not in AVATAR_FORMATS:
            raise AvatarError("头像只支持 JPG、PNG 或 WebP。")
        width, height = picture.size
        if width * height > AVATAR_MAX_PIXELS:
            raise AvatarError("图片太大了，请换一张 4000 万像素以内的。")
        if min(width, height) < AVATAR_MIN_SIDE:
            raise AvatarError(f"图片至少要 {AVATAR_MIN_SIDE}×{AVATAR_MIN_SIDE} 像素。")
        picture.seek(0)  # an animation keeps its first frame
        picture.load()
    except AvatarError:
        raise
    except Exception as error:  # noqa: BLE001 - any decoding failure
        raise AvatarError("读不出这张图片，请换一张 JPG、PNG 或 WebP。") from error
    picture = ImageOps.exif_transpose(picture)
    mode = "RGBA" if picture.mode in ("RGBA", "LA", "P") else "RGB"
    picture = picture.convert(mode)
    side = min(picture.size)
    left = (picture.width - side) // 2
    top = (picture.height - side) // 2
    picture = picture.crop((left, top, left + side, top + side))
    if side > AVATAR_SIDE:
        picture = picture.resize((AVATAR_SIDE, AVATAR_SIDE), PILImage.LANCZOS)
    out = BytesIO()
    picture.save(out, "WEBP", quality=88, method=6)
    return ContentFile(out.getvalue(), name=f"avatar-{secrets.token_hex(8)}.webp")


def create_face_image(uploaded, *, user):
    """A Wagtail image in the 用户头像 collection, from the upload."""
    from wagtail.images import get_image_model

    from content.services import ensure_user_avatar_collection

    face = square_face(uploaded)
    with PILImage.open(BytesIO(face.read())) as check:
        side = check.width
    face.seek(0)
    image = get_image_model()(
        title=f"头像 · {user.nickname}"[:255],
        file=face,
        width=side,
        height=side,
        collection=ensure_user_avatar_collection(),
        uploaded_by_user=user,
    )
    image.save()
    return image
