"""Weekly SQLite housekeeping (design 16.5, Sundays at 04:30)."""

from pathlib import Path

from django.core.management.base import BaseCommand
from django.db import OperationalError, connection

from core.dbfile import database_path


def _megabytes(path: Path) -> float:
    return path.stat().st_size / 1024 / 1024 if path.exists() else 0.0


class Command(BaseCommand):
    help = "执行 SQLite 的 PRAGMA optimize（设计 16.5）"

    def add_arguments(self, parser):
        parser.add_argument(
            "--vacuum",
            action="store_true",
            help="顺便执行 VACUUM。会重写整个数据库文件，耗时较长，默认不做。",
        )

    def handle(self, *args, **options):
        database = database_path()
        wal = database.with_name(database.name + "-wal")
        self.stdout.write(
            f"优化前：数据库 {_megabytes(database):.1f} MB，"
            f"WAL {_megabytes(wal):.1f} MB"
        )
        with connection.cursor() as cursor:
            cursor.execute("PRAGMA optimize")
            # A checkpoint needs every other connection to be idle. The worker
            # may well be mid-write at 04:30, and a skipped checkpoint costs
            # nothing but a larger WAL until the next run.
            try:
                cursor.execute("PRAGMA wal_checkpoint(TRUNCATE)")
            except OperationalError as exc:
                self.stdout.write(
                    self.style.WARNING(f"WAL 检查点跳过（数据库正忙）：{exc}")
                )
            if options["vacuum"]:
                try:
                    cursor.execute("VACUUM")
                except OperationalError as exc:
                    self.stdout.write(
                        self.style.WARNING(f"VACUUM 跳过（数据库正忙）：{exc}")
                    )
        self.stdout.write(
            self.style.SUCCESS(
                f"优化后：数据库 {_megabytes(database):.1f} MB，"
                f"WAL {_megabytes(wal):.1f} MB"
            )
        )
        return None
