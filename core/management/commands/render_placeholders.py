"""Write the placeholders to static/img/placeholders/ (design 13.2.5): the
covers, and the daylight versions of the hero and section pictures (v5.1).

Run after changing ``core/placeholders.py`` and commit the files. A test
redraws them and fails if the committed copies are out of date.
"""

from pathlib import Path

from django.conf import settings
from django.core.management.base import BaseCommand

from core import placeholders


class Command(BaseCommand):
    help = (
        "生成占位图：文章和赛事的封面，首屏和栏目横幅的白天版"
        "（static/img/placeholders/）。"
    )

    def handle(self, *args, **options):
        target = Path(settings.BASE_DIR) / "static" / placeholders.DIRECTORY
        target.mkdir(parents=True, exist_ok=True)
        files = placeholders.every_file()
        for name, svg in files.items():
            (target / name).write_text(svg, encoding="utf-8", newline="\n")
        ours = [*target.glob("cover-*.svg"), *target.glob("section-*.svg")]
        stale = [path for path in ours if path.name not in files]
        for path in stale:
            path.unlink()
        self.stdout.write(
            f"已生成 {len(files)} 张占位图到 {target}"
            + (f"，删除 {len(stale)} 张旧图" if stale else "")
        )
