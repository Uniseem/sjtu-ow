"""Take the camera's notes out of pictures stored before 219.

Until 219 a picture a visitor uploaded was kept as it came, in the public
``/media/original_images/`` folder under the name it had, and the address
follows from its thumbnail's. A phone photo carries the place, the device and
the time. New uploads are cleaned on the way in (``core/uploads.py``); this
command does the same for the ones already stored: only those that carry
something, only the original (thumbnails are written by Willow without it),
and the old file goes once the new one is saved.

Which pictures: those in 「投稿图片」 and 「队标」 and every team's logo
(add more with ``--collection``, or ``--all`` for the whole library; the
official covers and avatars the club uploads itself are left alone by
default). Team logos still in the shared collection move to 「队标」, which is
what lets a replaced logo take its file with it.

    manage.py scrub_originals --dry-run
    manage.py scrub_originals
"""

from __future__ import annotations

import io

from django.core.management.base import BaseCommand
from django.db import transaction
from django.db.models import Q
from PIL import Image as PILImage

from core.uploads import UploadError, clean_image

DEFAULT_COLLECTIONS = ("投稿图片", "队标")


def carries(image) -> tuple[bool, bool]:
    """(carries any metadata, carries a GPS position) for the stored original."""
    image.file.open("rb")
    try:
        with PILImage.open(io.BytesIO(image.file.read())) as picture:
            exif = picture.getexif()
            gps = bool(exif.get_ifd(0x8825)) if exif else False
            info = picture.info
            other = any(key in info for key in ("exif", "xmp", "XML:com.adobe.xmp"))
            tilted = bool(exif and exif.get(0x0112, 1) not in (0, 1))
            return bool(exif) or other or tilted, gps
    finally:
        image.file.close()


class Command(BaseCommand):
    help = "Re-encode stored original pictures that carry EXIF or GPS (219)."

    def add_arguments(self, parser):
        parser.add_argument("--dry-run", action="store_true", help="only list them")
        parser.add_argument(
            "--collection",
            action="append",
            default=[],
            help="one more collection to look through (repeatable)",
        )
        parser.add_argument(
            "--all", action="store_true", help="the whole library, not just uploads"
        )

    def targets(self, options):
        from wagtail.images import get_image_model

        from teams.models import Team

        images = get_image_model().objects.all()
        if not options["all"]:
            names = {*DEFAULT_COLLECTIONS, *options["collection"]}
            logo_ids = Team.objects.exclude(logo=None).values("logo_id")
            images = images.filter(Q(collection__name__in=names) | Q(pk__in=logo_ids))
        return images.select_related("collection").order_by("pk")

    def handle(self, *args, **options):
        dry = options["dry_run"]
        found = scrubbed = skipped = failed = moved = 0
        for image in self.targets(options):
            try:
                has_any, has_gps = carries(image)
            except Exception as error:  # noqa: BLE001
                failed += 1
                self.stderr.write(f"#{image.pk} {image.title}：读不出（{error}）")
                continue
            if self.move_logo(image, dry):
                moved += 1
            if not has_any:
                skipped += 1
                continue
            found += 1
            tag = "含 GPS" if has_gps else "含 EXIF"
            if dry:
                self.stdout.write(f"#{image.pk} {image.title}（{tag}）")
                continue
            try:
                self.scrub(image)
            except UploadError as error:
                failed += 1
                self.stderr.write(f"#{image.pk} {image.title}：{error}")
            else:
                scrubbed += 1
                self.stdout.write(f"#{image.pk} {image.title}（{tag}）已重新编码")
        verb = "会处理" if dry else "已处理"
        self.stdout.write(
            f"{verb} {found if dry else scrubbed} 张带信息的原图，"
            f"{skipped} 张本来就干净，{failed} 张处理不了，"
            f"{moved} 个队标{'会' if dry else '已'}移进「队标」集合。"
        )
        if scrubbed:
            self.stdout.write(
                "页面里的缩略图地址没变；要让静态页同步，跑一次 manage.py prerender。"
            )

    def move_logo(self, image, dry) -> bool:
        """A team's logo still in the shared collection goes to 「队标」."""
        from content.services import TEAM_LOGO_COLLECTION, ensure_team_logo_collection
        from teams.models import Team

        if image.collection.name == TEAM_LOGO_COLLECTION:
            return False
        if not Team.objects.filter(logo=image).exists():
            return False
        if not dry:
            image.collection = ensure_team_logo_collection()
            image.save(update_fields=["collection"])
        return True

    def scrub(self, image) -> None:
        image.file.open("rb")
        try:
            data = image.file.read()
        finally:
            image.file.close()
        clean = clean_image(io.BytesIO(data))
        old_name = image.file.name
        storage = image.file.storage
        with transaction.atomic():
            image.file.save(clean.name, clean, save=False)
            image.width, image.height = clean.width, clean.height
            image._set_image_file_metadata()
            image.save()
        storage.delete(old_name)
