"""Publish content/legal/*.md into the 用户协议 and 隐私政策 pages (design 16.4 step 8).

The drafts live in the repository so the club can review them as text, and
ship with the image (docs/ does not: .dockerignore leaves it out). Pages
that already have a body are left alone unless --force is given, so this never
overwrites what an editor has written in the admin.
"""

from __future__ import annotations

import html
import re
from pathlib import Path

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError
from wagtail.rich_text import RichText

from content.models import StandardPage

PAGES = (("terms", "terms.md"), ("privacy", "privacy.md"))
_COMMENT = re.compile(r"<!--.*?-->", re.S)
_BOLD = re.compile(r"\*\*(.+?)\*\*")
_ORDERED = re.compile(r"^\d+\.\s+")


def _inline(text: str) -> str:
    return _BOLD.sub(r"<b>\1</b>", html.escape(text.strip(), quote=False))


def markdown_to_html(source: str) -> str:
    """The small subset the drafts use: ## / ###, - and 1. lists, **bold**.

    The page title is the Wagtail title, so the draft's own # heading is dropped.
    """
    out: list[str] = []
    paragraph: list[str] = []
    list_tag = ""

    def flush_paragraph():
        if paragraph:
            # Chinese: joining lines with a space would leave 「。 第」 gaps.
            out.append(f"<p>{_inline(''.join(paragraph))}</p>")
            paragraph.clear()

    def close_list():
        nonlocal list_tag
        if list_tag:
            out.append(f"</{list_tag}>")
            list_tag = ""

    for raw in _COMMENT.sub("", source).splitlines():
        line = raw.rstrip()
        if not line.strip():
            flush_paragraph()
            close_list()
            continue
        if line.startswith("# "):
            continue
        heading = re.match(r"^(#{2,3})\s+(.*)$", line)
        if heading:
            flush_paragraph()
            close_list()
            level = len(heading.group(1))
            out.append(f"<h{level}>{_inline(heading.group(2))}</h{level}>")
            continue
        item_tag = ""
        if line.startswith("- "):
            item_tag = "ul"
        elif _ORDERED.match(line):
            item_tag = "ol"
        if item_tag:
            flush_paragraph()
            if list_tag != item_tag:
                close_list()
                out.append(f"<{item_tag}>")
                list_tag = item_tag
            text = line[2:] if item_tag == "ul" else _ORDERED.sub("", line)
            out.append(f"<li>{_inline(text)}</li>")
            continue
        close_list()
        paragraph.append(line)
    flush_paragraph()
    close_list()
    return "".join(out)


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
            page.body = [("paragraph", RichText(markdown_to_html(text)))]
            page.save_revision().publish()
            self.stdout.write(self.style.SUCCESS(f"已发布「{page.title}」"))
