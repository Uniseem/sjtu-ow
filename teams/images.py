"""Turn an uploaded team logo into a Wagtail image (design 7.1), and take it
away again when nobody uses it."""

from __future__ import annotations

from core.uploads import CleanImage, clean_image

LOGO_MAX_SIDE = 1024


def clean_logo(uploaded) -> CleanImage:
    """The upload as the picture we keep (219): checked, upright, at most
    1024 pixels a side, no EXIF, a random name. ``UploadError`` if it is not
    a picture we can use."""
    return clean_image(uploaded, max_side=LOGO_MAX_SIDE)


def create_logo(uploaded, *, title: str, user=None):
    from wagtail.images import get_image_model

    from content.services import ensure_team_logo_collection

    clean = clean_logo(uploaded)
    image = get_image_model()(
        title=title[:255],
        file=clean,
        width=clean.width,
        height=clean.height,
        collection=ensure_team_logo_collection(),
        uploaded_by_user=user if getattr(user, "pk", None) else None,
    )
    image.save()
    return image


def discard_logo(image) -> None:
    """A logo no team uses any more goes, with its file and thumbnails (219,
    217 review 07-11). Only one made here, in the 队标 collection: an older
    logo in the shared collection, or a picture an editor chose from the
    library, is not ours to delete."""
    from content.services import TEAM_LOGO_COLLECTION
    from teams.models import Team

    if image is None or image.collection.name != TEAM_LOGO_COLLECTION:
        return
    if Team.objects.filter(logo=image).exists():
        return
    image.delete()
