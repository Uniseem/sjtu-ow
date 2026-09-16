"""Turn an uploaded team logo into a Wagtail image (design 7.1)."""

from __future__ import annotations


def create_logo(uploaded, *, title: str, user=None):
    from wagtail.images import get_image_model
    from willow.image import Image as WillowImage

    Image = get_image_model()
    uploaded.seek(0)
    willow = WillowImage.open(uploaded)
    width, height = willow.get_size()
    uploaded.seek(0)
    image = Image(
        title=title[:255],
        file=uploaded,
        width=width,
        height=height,
        uploaded_by_user=user if getattr(user, "pk", None) else None,
    )
    image.save()
    return image
