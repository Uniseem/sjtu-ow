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
        parser.add_argument(
            "--no-upload",
            action="store_true",
            help="即使后台开了异地备份，这次也不上传。",
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
        self.upload(archive, skip=options["no_upload"], keep_days=keep_days)
        return None

    def upload(self, archive: Path, *, skip: bool, keep_days: int) -> None:
        """Design 16.7 step 3: encrypt and send a copy off the server."""
        from core import offsite

        config = offsite.load_config()
        if not config.enabled:
            self.stdout.write(
                self.style.WARNING(
                    "异地备份没有开启。本地这份没有加密，里面有用户邮箱和联系方式，"
                    "**服务器没了这份也跟着没了**。"
                    "在「设置 → 全站设置 → 异地备份」里配置对象存储（设计 16.7）。"
                )
            )
            return
        if skip:
            self.stdout.write("按 --no-upload 跳过上传。")
            return
        try:
            key = offsite.upload(archive, config=config)
        except offsite.OffsiteError as exc:
            # A failed upload must not look like a successful backup.
            raise CommandError(f"本地备份已生成，但上传失败：{exc}") from exc
        self.stdout.write(self.style.SUCCESS(f"已加密并上传到 {config.bucket}/{key}"))
        try:
            removed = offsite.prune(keep_days, config=config)
        except offsite.OffsiteError as exc:
            # Nothing is lost if the old copies stay one more day.
            self.stdout.write(self.style.WARNING(f"异地旧备份没清理掉：{exc}"))
        else:
            if removed:
                self.stdout.write(f"已清理异地 {removed} 个超过 {keep_days} 天的旧备份")

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
