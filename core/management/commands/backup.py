"""Back up the database and uploads (design 16.7, run daily at 03:00).

The database is snapshotted through SQLite's online backup API, never by
copying the file: with WAL enabled a plain copy can catch a torn state,
and the WAL itself would be left behind.

``static`` and ``prerendered`` are not backed up -- both can be rebuilt.
"""

from __future__ import annotations

import sqlite3
import tarfile
import tempfile
from datetime import timedelta
from pathlib import Path

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError
from django.utils import timezone

STAMP = "%Y%m%d-%H%M%S"
PREFIX = "sjtu-ow-"
SUFFIX = ".tar.gz"


def backup_root() -> Path:
    return Path(getattr(settings, "BACKUP_ROOT", Path("backups")))


def snapshot_database(target: Path) -> None:
    """Design 16.7 step 1: SQLite's online backup, not a file copy."""
    from core.dbfile import database_path

    source = sqlite3.connect(f"file:{database_path()}?mode=ro", uri=True, timeout=30)
    try:
        destination = sqlite3.connect(str(target))
        try:
            source.backup(destination)
        finally:
            destination.close()
    finally:
        source.close()


def existing_backups(root: Path) -> list[Path]:
    return sorted(root.glob(f"{PREFIX}*{SUFFIX}"))


class Command(BaseCommand):
    help = "备份数据库和上传文件（设计 16.7）"

    def add_arguments(self, parser):
        parser.add_argument("--output", help="备份目录，默认取设置里的 BACKUP_ROOT。")
        parser.add_argument(
            "--keep-days",
            type=int,
            help="保留天数，默认取设置里的 BACKUP_KEEP_DAYS（14）。",
        )

    def handle(self, *args, **options):
        root = Path(options["output"]) if options["output"] else backup_root()
        keep_days = options["keep_days"] or int(
            getattr(settings, "BACKUP_KEEP_DAYS", 14)
        )
        root.mkdir(parents=True, exist_ok=True)

        stamp = timezone.localtime().strftime(STAMP)
        archive = root / f"{PREFIX}{stamp}{SUFFIX}"
        if archive.exists():
            raise CommandError(f"{archive} 已经存在。")

        with tempfile.TemporaryDirectory() as workspace:
            staged = Path(workspace) / "db.sqlite3"
            snapshot_database(staged)
            with tarfile.open(archive, "w:gz") as bundle:
                bundle.add(staged, arcname="db.sqlite3")
                media = Path(settings.MEDIA_ROOT)
                if media.exists():
                    bundle.add(media, arcname="media")

        size_mb = archive.stat().st_size / 1024 / 1024
        self.stdout.write(self.style.SUCCESS(f"已备份到 {archive}（{size_mb:.1f} MB）"))
        removed = self.prune(root, keep_days)
        if removed:
            self.stdout.write(f"已清理 {removed} 个超过 {keep_days} 天的旧备份")
        self.stdout.write(
            self.style.WARNING(
                "备份里有用户邮箱和联系方式，且没有加密。"
                "上传到服务器以外的位置之前先加密（设计 16.7）。"
            )
        )
        return None

    def prune(self, root: Path, keep_days: int) -> int:
        cutoff = timezone.now() - timedelta(days=keep_days)
        removed = 0
        for path in existing_backups(root):
            stamp = path.name[len(PREFIX) : -len(SUFFIX)]
            try:
                made = timezone.make_aware(
                    timezone.datetime.strptime(stamp, STAMP),
                    timezone.get_current_timezone(),
                )
            except ValueError:
                continue  # not one of ours; leave it alone
            if made < cutoff:
                path.unlink()
                removed += 1
        return removed
