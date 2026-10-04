"""Publish content/legal/*.md into the 用户协议 and 隐私政策 pages (design 16.4 step 8).

The drafts live in the repository so the club can review them as text, and
ship with the image (docs/ does not: .dockerignore leaves it out). Pages
that already have a body are left alone unless --force is given, so this never
overwrites what an editor has written in the admin.
"""

from __future__ import annotations

import re
from pathlib import Path

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError

from content.models import StandardPage

PAGES = (("terms", "terms.md"), ("privacy", "privacy.md"))
_COMMENT = re.compile(r"<!--.*?-->", re.S)
_TITLE = re.compile(r"^# [^\n]*\n?", re.M)


def body_from_draft(source: str) -> str:
    """The draft as the page body (Markdown, design 5.2 v6.70): without the
    note to the club at the top, and without its own # title, which is the
    page title."""
    return _TITLE.sub("", _COMMENT.sub("", source), count=1).strip()


class Command(BaseCommand):
    help = "把 content/legal/ 里的用户协议和隐私政策草稿发布到网站对应页面。"

    def add_arguments(self, parser):
        parser.add_argument(
            "--force",
            action="store_true",
            help="页面已经有正文时也覆盖（默认跳过，不覆盖后台里写的内容）",
        )
        parser.add_argument(
            "--source",
            type=Path,
            default=None,
            help="草稿所在目录，默认是 content/legal/",
        )

    def handle(self, *args, **options):
        source = options["source"] or Path(settings.BASE_DIR) / "content" / "legal"
        for slug, filename in PAGES:
            page = StandardPage.objects.filter(slug=slug).first()
            if page is None:
                raise CommandError(f"没有找到 /{slug}/ 页面，先运行 init_site。")
            if page.body and not options["force"]:
                self.stdout.write(f"「{page.title}」已有正文，跳过（覆盖请加 --force）")
                continue
            text = (source / filename).read_text(encoding="utf-8")
            page.body = body_from_draft(text)
            page.save_revision().publish()
            self.stdout.write(self.style.SUCCESS(f"已发布「{page.title}」"))
