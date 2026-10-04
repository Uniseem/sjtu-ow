"""Draw the site icon in the sizes browsers and phones ask for (design 13.2.5).

Run after core/icons.py changes and commit the files. A test draws them again
and fails if the committed ones are out of date.
"""

from pathlib import Path

from django.conf import settings
from django.core.management.base import BaseCommand

from core import icons


class Command(BaseCommand):
    help = (
        "按 favicon.svg 的形状画出 favicon.ico、apple-touch-icon 和网页清单用的图标。"
    )

    def handle(self, *args, **options):
        folder = Path(settings.BASE_DIR) / "static" / "img"
        for path in icons.write(folder):
            self.stdout.write(
                f"已生成 {path.relative_to(settings.BASE_DIR).as_posix()}"
            )
