"""Write the cover placeholders to static/img/placeholders/ (design 13.2.5).

Run after changing ``core/placeholders.py`` and commit the files. A test
redraws them and fails if the committed copies are out of date.
"""

from pathlib import Path

from django.conf import settings
from django.core.management.base import BaseCommand

from core import placeholders


class Command(BaseCommand):
    help = "生成文章和赛事没有封面时用的占位图（static/img/placeholders/）。"

    def handle(self, *args, **options):
        target = Path(settings.BASE_DIR) / "static" / placeholders.DIRECTORY
        target.mkdir(parents=True, exist_ok=True)
        wanted = set()
        for index in range(len(placeholders.CATALOGUE)):
            name = placeholders.filename(index)
            wanted.add(name)
            (target / name).write_text(
                placeholders.render(index), encoding="utf-8", newline="\n"
            )
        stale = [p for p in target.glob("cover-*.svg") if p.name not in wanted]
        for path in stale:
            path.unlink()
        self.stdout.write(
            f"已生成 {len(wanted)} 张占位图到 {target}"
            + (f"，删除 {len(stale)} 张旧图" if stale else "")
        )
