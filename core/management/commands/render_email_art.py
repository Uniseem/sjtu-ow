"""Draw the pictures inside every letter: the site mark and the ridges along
the head (design 10.3, v7.4).

Run after core/email_art.py (or the site's horizon or icon numbers) changes
and commit the files. A test draws them again and fails if the committed ones
are out of date.
"""

from django.conf import settings
from django.core.management.base import BaseCommand

from core import email_art


class Command(BaseCommand):
    help = "画出邮件页头的站点标志和两道山脊（static/img/email/）。"

    def handle(self, *args, **options):
        for path in email_art.write():
            self.stdout.write(
                f"已生成 {path.relative_to(settings.BASE_DIR).as_posix()}"
            )
