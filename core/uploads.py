"""The one way a picture a visitor sends becomes a picture we keep (219).

Before this, every door had its own care: the avatar was re-encoded (so no
place, device or time survived), the team logo and everything uploaded through
Wagtail's image form was stored as it came, original file name and EXIF block
included, in a public folder whose address follows from the thumbnail's. A
JPEG with a broken EXIF block decoded fine and then made every page showing it
a 500 (217 review 07-1); a 144-megapixel PNG of a few hundred KB cost 430 MB
for each thumbnail (07-2); a phone photo gave its GPS position to anyone
(07-3, 02-1).

``clean_image`` is what all of them go through: read the header and refuse
what is too large before decoding anything, accept only JPEG, PNG and WebP by
what the file *is* rather than what it is called, keep the first frame of an
animation, turn it upright (a broken EXIF block means refusal, not a 500),
shrink to ``max_side`` and write it again as WebP under a random name. Nothing
the camera put in the file survives.
"""

from __future__ import annotations

import secrets
import warnings
from io import BytesIO

from django.core.files.base import ContentFile
from PIL import Image as PILImage
from PIL import ImageOps

IMAGE_FORMATS = {"JPEG", "PNG", "WEBP"}
MAX_PIXELS = 40_000_000  # far below Pillow's bomb limit, still any photo
MAX_SIDE = 4096

# Pictures a person may add in a day, through any door. Superusers have no
# limit; the content editors upload event photos in batches of up to 50.
UPLOADS_PER_DAY = 40
EDITOR_UPLOADS_PER_DAY = 300
EDITOR_GROUP = "内容编辑"
TOO_MANY = "今天上传的图片太多了，明天再试。"


class UploadError(ValueError):
    """The upload is not a picture we keep; the message is for the person."""


class CleanImage(ContentFile):
    """A picture that went through ``clean_image``; later steps need not do it
    again, and read its size from here."""

    width: int
    height: int


def clean_image(
    uploaded, *, max_pixels: int = MAX_PIXELS, max_side: int = MAX_SIDE
) -> CleanImage:
    """The upload as a WebP of at most ``max_side`` pixels, or ``UploadError``."""
    if isinstance(uploaded, CleanImage):
        return uploaded
    uploaded.seek(0)
    try:
        with warnings.catch_warnings():
            # Pillow only warns between its two limits; our own limit is the
            # one that counts, and it speaks Chinese.
            warnings.simplefilter("ignore", PILImage.DecompressionBombWarning)
            picture = PILImage.open(uploaded)
            if picture.format not in IMAGE_FORMATS:
                raise UploadError("图片只支持 JPG、PNG 或 WebP。")
            width, height = picture.size  # from the header: nothing decoded yet
            if width * height > max_pixels:
                raise UploadError(
                    f"图片太大了，请换一张 {max_pixels // 10_000} 万像素以内的。"
                )
            picture.seek(0)  # an animation keeps its first frame
            picture.load()
            # Inside the try (216, A4): a JPEG whose EXIF block is garbage, or
            # a PNG with a malformed "Raw profile type exif" chunk, decodes
            # fine and only fails here. That was a 500.
            picture = ImageOps.exif_transpose(picture)
    except UploadError:
        raise
    except Exception as error:  # noqa: BLE001 - any decoding failure
        raise UploadError("读不出这张图片，请换一张 JPG、PNG 或 WebP。") from error
    mode = "RGBA" if picture.mode in ("RGBA", "LA", "P") else "RGB"
    picture = picture.convert(mode)
    if max(picture.size) > max_side:
        picture.thumbnail((max_side, max_side), PILImage.LANCZOS)
    out = BytesIO()
    picture.save(out, "WEBP", quality=90, method=4)
    clean = CleanImage(out.getvalue(), name=f"upload-{secrets.token_hex(10)}.webp")
    clean.width, clean.height = picture.size
    return clean


def uploads_per_day(user) -> int | None:
    """How many pictures this person may add in a day; None for no limit."""
    if getattr(user, "is_superuser", False):
        return None
    if user.groups.filter(name=EDITOR_GROUP).exists():
        return EDITOR_UPLOADS_PER_DAY
    return UPLOADS_PER_DAY


def over_daily_limit(user) -> bool:
    """Count one more picture for this person; True once the day's are used."""
    from core.ratelimit import over_limit

    limit = uploads_per_day(user)
    if limit is None:
        return False
    return over_limit(f"upload:{user.pk}", limit, 86400)
