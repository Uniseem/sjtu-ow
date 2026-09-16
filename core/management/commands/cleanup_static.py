"""Drop static files no version still uses (design 16.5, daily at 04:20).

An upgrade adds the new build's hashed files and leaves the old ones in
place (design 16.8 step 5), so visitors holding a cached page can still
fetch the assets it references. A month later they are safe to remove.

"Still in use" means "named in the current ``staticfiles.json`` manifest",
so a file is only deleted when it is both absent from the manifest and
older than the retention window.
"""

from __future__ import annotations

import json
from datetime import timedelta
from pathlib import Path

from django.conf import settings
from django.core.management.base import BaseCommand
from django.utils import timezone

MANIFEST = "staticfiles.json"
# The manifest lists the plain file; whitenoise writes these next to it.
COMPANION_SUFFIXES = (".gz", ".br")


def manifest_paths(root: Path) -> set[str]:
    """Every path the current build refers to, companions included."""
    manifest = root / MANIFEST
    if not manifest.exists():
        return set()
    try:
        data = json.loads(manifest.read_text())
    except (ValueError, OSError):
        return set()
    names = set(data.get("paths", {}).values())
    names.update(data.get("paths", {}).keys())
    current = set()
    for name in names:
        current.add(name)
        for suffix in COMPANION_SUFFIXES:
            current.add(name + suffix)
    return current


class Command(BaseCommand):
    help = "清理 static 数据卷里不属于当前版本的旧文件（设计 16.5）"

    def add_arguments(self, parser):
        parser.add_argument("--dry-run", action="store_true", help="只统计不删除。")
        parser.add_argument(
            "--keep-days",
            type=int,
            help="保留天数，默认取设置里的 STATIC_KEEP_DAYS（30）。",
        )

    def handle(self, *args, **options):
        root = Path(settings.STATIC_ROOT)
        keep_days = options["keep_days"] or int(
            getattr(settings, "STATIC_KEEP_DAYS", 30)
        )
        if not root.exists():
            self.stdout.write(f"{root} 不存在，跳过。")
            return None

        current = manifest_paths(root)
        if not current:
            self.stdout.write(
                self.style.WARNING(
                    f"{root / MANIFEST} 不存在或读不出来。"
                    "没有清单就无法判断哪些文件还在用，什么都不删。"
                )
            )
            return None

        cutoff = (timezone.now() - timedelta(days=keep_days)).timestamp()
        removed = 0
        freed = 0
        kept_recent = 0
        for path in sorted(root.rglob("*")):
            if path.is_dir():
                continue
            relative = path.relative_to(root).as_posix()
            if relative == MANIFEST or relative in current:
                continue
            if path.stat().st_mtime >= cutoff:
                kept_recent += 1
                continue
            freed += path.stat().st_size
            if not options["dry_run"]:
                path.unlink()
            removed += 1

        if not options["dry_run"]:
            self._prune_empty_dirs(root)

        verb = "将删除" if options["dry_run"] else "已删除"
        self.stdout.write(
            f"{verb} {removed} 个旧静态文件（{freed / 1024 / 1024:.1f} MB）；"
            f"保留当前版本的 {len(current)} 条清单项，"
            f"另有 {kept_recent} 个文件未超过 {keep_days} 天。"
        )
        return None

    @staticmethod
    def _prune_empty_dirs(root: Path) -> None:
        for path in sorted(root.rglob("*"), reverse=True):
            if path.is_dir() and not any(path.iterdir()):
                path.rmdir()
