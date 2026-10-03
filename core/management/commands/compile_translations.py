"""Compile the project's .po files into .mo without GNU gettext (round 117)."""

from django.conf import settings
from django.core.management.base import BaseCommand

from core.translations import compiled, po_files


class Command(BaseCommand):
    help = (
        "把 locale/ 下的 .po 编成 .mo（只用标准库，不需要 gettext）。"
        "改了 .po 后运行并提交 .mo。"
    )

    def handle(self, *args, **options):
        files = po_files(settings.LOCALE_PATHS)
        if not files:
            self.stdout.write("没有找到 .po 文件。")
            return
        for po_path in files:
            mo_path = po_path.with_suffix(".mo")
            data = compiled(po_path)
            if mo_path.exists() and mo_path.read_bytes() == data:
                self.stdout.write(f"没有变化：{mo_path}")
                continue
            mo_path.write_bytes(data)
            self.stdout.write(self.style.SUCCESS(f"已生成：{mo_path}"))
