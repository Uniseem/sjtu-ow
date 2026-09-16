"""Restore from a backup (design 16.7).

What this command can do: replace the database (WAL files included),
restore ``media``, and clear ``prerendered`` so the static pages cannot be
newer than the data. Stopping and starting the services is the operator's
job -- the reminders are printed.

Before touching anything it checks that ``FIELD_ENCRYPTION_KEY`` still
decrypts the backup's encrypted fields. Restoring under the wrong key
would leave a database full of ciphertext nobody can read.
"""

from __future__ import annotations

import shutil
import sqlite3
import tarfile
import tempfile
from pathlib import Path

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError
from django.db import connection

from core.dbfile import database_path, wal_siblings

# (table, column) pairs holding Fernet ciphertext.
ENCRYPTED_COLUMNS = (
    ("core_sitesettings", "smtp_password"),
    ("integrations_apiclient", "secret"),
    ("integrations_apiclient", "webhook_secret"),
)


def check_key(snapshot: Path) -> list[str]:
    """Return the fields the current key cannot decrypt."""
    from core.crypto import decrypt_value, looks_like_fernet

    broken = []
    connection = sqlite3.connect(f"file:{snapshot}?mode=ro", uri=True)
    try:
        for table, column in ENCRYPTED_COLUMNS:
            try:
                rows = connection.execute(
                    f"SELECT {column} FROM {table} WHERE {column} != ''"  # noqa: S608
                ).fetchall()
            except sqlite3.OperationalError:
                continue  # table not in this backup
            for (value,) in rows:
                if not value or not looks_like_fernet(value):
                    continue
                try:
                    decrypt_value(value)
                except ValueError:
                    broken.append(f"{table}.{column}")
                    break
    finally:
        connection.close()
    return broken


class Command(BaseCommand):
    help = "从备份恢复数据库和上传文件（设计 16.7）"

    def show_listing(self):
        from core import offsite

        try:
            items = offsite.listing()
        except offsite.OffsiteError as exc:
            raise CommandError(str(exc)) from exc
        if not items:
            self.stdout.write("对象存储里没有备份。")
            return None
        for item in items:
            size_mb = item.get("Size", 0) / 1024 / 1024
            self.stdout.write(
                f"  {item['Key']}  {size_mb:.1f} MB  {item.get('LastModified', '')}"
            )
        self.stdout.write("")
        self.stdout.write("用 --from-s3 <KEY> 恢复其中一个。")
        return None

    def add_arguments(self, parser):
        parser.add_argument(
            "archive",
            nargs="?",
            help="备份文件，比如 backups/sjtu-ow-...tar.gz。用 --from-s3 时可以不填。",
        )
        parser.add_argument(
            "--from-s3",
            metavar="KEY",
            help="先从对象存储下载这个对象并解密（用 --list-s3 看有哪些）。",
        )
        parser.add_argument(
            "--list-s3",
            action="store_true",
            help="列出对象存储里的备份，不做任何恢复。",
        )
        parser.add_argument(
            "--yes",
            action="store_true",
            help="真的执行。不加这个参数只打印将要做什么。",
        )
        parser.add_argument(
            "--skip-key-check",
            action="store_true",
            help="跳过 FIELD_ENCRYPTION_KEY 校验（不建议）。",
        )

    def handle(self, *args, **options):
        from core import offsite

        if options["list_s3"]:
            return self.show_listing()

        downloaded = None
        if options["from_s3"]:
            downloaded = tempfile.mkdtemp(prefix="restore-")
            target = Path(downloaded) / "downloaded.tar.gz"
            self.stdout.write(f"正在从对象存储下载 {options['from_s3']} ……")
            try:
                offsite.download(options["from_s3"], target)
            except offsite.OffsiteError as exc:
                raise CommandError(str(exc)) from exc
            self.stdout.write("下载并解密完成。")
            archive = target
        elif options["archive"]:
            archive = Path(options["archive"])
        else:
            raise CommandError("要么给出备份文件路径，要么用 --from-s3。")

        if not archive.exists():
            raise CommandError(f"找不到备份文件 {archive}。")

        database = database_path()
        media = Path(settings.MEDIA_ROOT)
        prerendered = Path(getattr(settings, "PRERENDER_ROOT", "prerendered"))
        dry_run = not options["yes"]

        with tempfile.TemporaryDirectory() as workspace:
            staging = Path(workspace)
            with tarfile.open(archive, "r:gz") as bundle:
                bundle.extractall(staging, filter="data")
            snapshot = staging / "db.sqlite3"
            if not snapshot.exists():
                raise CommandError("备份里没有 db.sqlite3。")

            if not options["skip_key_check"]:
                broken = check_key(snapshot)
                if broken:
                    raise CommandError(
                        "当前的 FIELD_ENCRYPTION_KEY 解不开备份里的加密字段："
                        f"{'、'.join(sorted(set(broken)))}。"
                        "请换成备份时使用的密钥再恢复（设计 16.7 第 3 步）。"
                    )
                self.stdout.write("FIELD_ENCRYPTION_KEY 校验通过。")

            plan = [
                f"用备份里的数据库替换 {database}",
                f"删除 WAL 文件：{', '.join(str(p) for p in wal_siblings(database))}",
                f"恢复 media 到 {media}",
                f"清空 {prerendered}",
            ]
            for line in plan:
                self.stdout.write(f"  - {line}")

            if dry_run:
                self.stdout.write(
                    self.style.WARNING("这是演练，什么都没有改。加 --yes 才会执行。")
                )
                return None

            # Close our own connection and drop the old WAL *before* the new
            # file lands. Replacing the database underneath an open connection
            # risks SQLite replaying the previous WAL into the fresh file.
            connection.close()
            database.parent.mkdir(parents=True, exist_ok=True)
            for path in wal_siblings(database):
                if path.exists():
                    path.unlink()
            shutil.copy2(snapshot, database)

            staged_media = staging / "media"
            if staged_media.exists():
                if media.exists():
                    shutil.rmtree(media)
                shutil.copytree(staged_media, media)

            if prerendered.exists():
                for child in prerendered.iterdir():
                    if child.is_dir():
                        shutil.rmtree(child)
                    else:
                        child.unlink()

        from core.models import PrerenderedPage

        PrerenderedPage.objects.all().delete()

        self.stdout.write(self.style.SUCCESS("恢复完成。"))
        self.warn_if_code_is_newer()
        self.stdout.write(
            "接下来（设计 16.7）：启动 web 和 worker，在后台触发全量重新生成，"
            "检查 /healthz 和关键页面。"
        )
        return None

    def warn_if_code_is_newer(self) -> None:
        """Design 16.8 step 8: a rollback also has to go back to the old image.

        Restoring a pre-upgrade backup while the new code is still running
        leaves the schema behind what the code expects. Django will not say
        so until something touches a missing column, which in a rollback is
        exactly the wrong moment to find out.
        """
        from django.db import connection as db
        from django.db.migrations.executor import MigrationExecutor

        try:
            executor = MigrationExecutor(db)
            plan = executor.migration_plan(executor.loader.graph.leaf_nodes())
        except Exception:  # noqa: BLE001 — a warning must never fail a restore
            return
        if not plan:
            return
        names = ", ".join(
            f"{migration.app_label}.{migration.name}" for migration, _ in plan[:5]
        )
        more = "……" if len(plan) > 5 else ""
        self.stdout.write(
            self.style.WARNING(
                f"注意：恢复的数据库比当前代码旧，还差 {len(plan)} 个迁移"
                f"（{names}{more}）。\n"
                "如果这是升级后的回滚（设计 16.8 第 8 步），**要切回旧镜像**，"
                "不要用当前代码继续跑——schema 对不上，出问题时才会报错。\n"
                "如果你确实想让当前代码用这份数据，执行 manage.py migrate。"
            )
        )
