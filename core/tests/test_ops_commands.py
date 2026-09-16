"""Design 16.5 and 16.7: backup, restore, static cleanup, SQLite optimize."""

import json
import shutil
import sqlite3
import tarfile
import threading
import time
from datetime import timedelta
from io import StringIO
from pathlib import Path

import pytest
from django.core.management import call_command
from django.core.management.base import CommandError
from django.utils import timezone

from core.management.commands import backup as backup_command


def run(command, *args, **kwargs):
    out = StringIO()
    call_command(command, *args, stdout=out, stderr=out, **kwargs)
    return out.getvalue()


@pytest.fixture
def backups(tmp_path):
    root = tmp_path / "backups"
    root.mkdir()
    return root


# --- backup --------------------------------------------------------------------


@pytest.mark.django_db
def test_backup_writes_an_archive_with_the_database(backups, settings, tmp_path):
    settings.MEDIA_ROOT = tmp_path / "media"
    settings.MEDIA_ROOT.mkdir()
    (settings.MEDIA_ROOT / "logo.png").write_bytes(b"not really a png")

    output = run("backup", "--output", str(backups))

    archives = list(backups.glob("sjtu-ow-*.tar.gz"))
    assert len(archives) == 1
    assert "已备份到" in output
    assert "没有加密" in output  # design 16.7: say so before anyone uploads it

    with tarfile.open(archives[0], "r:gz") as bundle:
        names = bundle.getnames()
    assert "db.sqlite3" in names
    assert "media/logo.png" in names


@pytest.mark.django_db
def test_backup_does_not_include_prerendered_or_static(backups, settings, tmp_path):
    settings.MEDIA_ROOT = tmp_path / "media"
    settings.MEDIA_ROOT.mkdir()

    run("backup", "--output", str(backups))

    with tarfile.open(next(backups.glob("*.tar.gz")), "r:gz") as bundle:
        names = bundle.getnames()
    assert not any(name.startswith("prerendered") for name in names)
    assert not any(name.startswith("staticfiles") for name in names)
    assert not any(name.endswith(".env") for name in names)


@pytest.mark.django_db(transaction=True)
def test_the_snapshot_is_a_readable_database(backups, settings, tmp_path):
    """Needs a real commit: the snapshot reads the file, not our transaction."""
    from accounts.models import User

    settings.MEDIA_ROOT = tmp_path / "media"
    settings.MEDIA_ROOT.mkdir()
    now = timezone.now()
    User.objects.create_user(
        email="backed-up@example.com",
        password="Correct-Horse-Battery-1",
        nickname="备份用户",
        agreed_terms_at=now,
        agreed_cross_border_at=now,
    )

    run("backup", "--output", str(backups))

    extracted = tmp_path / "check"
    extracted.mkdir()
    with tarfile.open(next(backups.glob("*.tar.gz")), "r:gz") as bundle:
        bundle.extractall(extracted, filter="data")
    connection = sqlite3.connect(extracted / "db.sqlite3")
    try:
        emails = [
            row[0]
            for row in connection.execute("SELECT email FROM accounts_user").fetchall()
        ]
    finally:
        connection.close()
    assert "backed-up@example.com" in emails


@pytest.mark.django_db(transaction=True)
def test_the_snapshot_is_consistent_while_writes_are_happening(
    backups, settings, tmp_path
):
    """The reason for the online backup API instead of copying the file.

    A plain copy of a WAL database mid-write can land on a torn state; the
    snapshot must always open cleanly and pass an integrity check.
    """
    from accounts.models import User

    settings.MEDIA_ROOT = tmp_path / "media"
    settings.MEDIA_ROOT.mkdir()
    stop = threading.Event()

    def churn():
        from django.db import connection as writer

        index = 0
        while not stop.is_set() and index < 200:
            now = timezone.now()
            User.objects.create_user(
                email=f"churn{index}@example.com",
                password="Correct-Horse-Battery-1",
                nickname=f"写入{index}",
                agreed_terms_at=now,
                agreed_cross_border_at=now,
            )
            index += 1
            time.sleep(0.001)
        writer.close()

    worker = threading.Thread(target=churn, daemon=True)
    worker.start()
    time.sleep(0.05)
    try:
        run("backup", "--output", str(backups))
    finally:
        stop.set()
        worker.join(timeout=10)
    # A writer thread that outlived this test would hold a connection and keep
    # inserting rows while later tests run, which is a miserable thing to debug.
    assert not worker.is_alive(), "写入线程没有在测试结束前停下"

    extracted = tmp_path / "check"
    extracted.mkdir()
    with tarfile.open(next(backups.glob("*.tar.gz")), "r:gz") as bundle:
        bundle.extractall(extracted, filter="data")
    connection = sqlite3.connect(extracted / "db.sqlite3")
    try:
        assert connection.execute("PRAGMA integrity_check").fetchone()[0] == "ok"
        # And it is a real database, not an empty file.
        connection.execute("SELECT COUNT(*) FROM accounts_user").fetchone()
    finally:
        connection.close()


@pytest.mark.django_db
def test_old_backups_are_pruned_and_recent_ones_kept(backups, settings, tmp_path):
    settings.MEDIA_ROOT = tmp_path / "media"
    settings.MEDIA_ROOT.mkdir()
    now = timezone.localtime()
    stale = now - timedelta(days=20)
    fresh = now - timedelta(days=3)
    for moment in (stale, fresh):
        name = f"sjtu-ow-{moment.strftime(backup_command.STAMP)}.tar.gz"
        (backups / name).write_bytes(b"old archive")
    unrelated = backups / "keep-me.txt"
    unrelated.write_text("not a backup")

    output = run("backup", "--output", str(backups), "--keep-days", "14")

    names = sorted(path.name for path in backups.glob("*"))
    assert f"sjtu-ow-{stale.strftime(backup_command.STAMP)}.tar.gz" not in names
    assert f"sjtu-ow-{fresh.strftime(backup_command.STAMP)}.tar.gz" in names
    assert unrelated.name in names  # never touch files that are not ours
    assert "已清理 1 个" in output


@pytest.mark.django_db
def test_keep_days_is_honoured(backups, settings, tmp_path):
    settings.MEDIA_ROOT = tmp_path / "media"
    settings.MEDIA_ROOT.mkdir()
    old = timezone.localtime() - timedelta(days=5)
    name = f"sjtu-ow-{old.strftime(backup_command.STAMP)}.tar.gz"
    (backups / name).write_bytes(b"five days old")

    run("backup", "--output", str(backups), "--keep-days", "3")

    assert not (backups / name).exists()


# --- restore -------------------------------------------------------------------


def make_backup(backups, settings, tmp_path):
    settings.MEDIA_ROOT = tmp_path / "media"
    settings.MEDIA_ROOT.mkdir(exist_ok=True)
    run("backup", "--output", str(backups))
    return next(backups.glob("*.tar.gz"))


@pytest.mark.django_db
def test_restore_without_yes_changes_nothing(backups, settings, tmp_path):
    from accounts.models import User

    archive = make_backup(backups, settings, tmp_path)
    now = timezone.now()
    User.objects.create_user(
        email="after-backup@example.com",
        password="Correct-Horse-Battery-1",
        nickname="备份之后",
        agreed_terms_at=now,
        agreed_cross_border_at=now,
    )
    prerendered = tmp_path / "prerendered"
    prerendered.mkdir()
    (prerendered / "index.html").write_text("stale page")
    settings.PRERENDER_ROOT = prerendered

    output = run("restore", str(archive))

    assert "演练" in output
    assert (prerendered / "index.html").exists()
    assert User.objects.filter(email="after-backup@example.com").exists()


@pytest.mark.django_db(transaction=True)
def test_restore_refuses_a_mismatched_encryption_key(
    backups, settings, tmp_path, monkeypatch
):
    """Design 16.7 step 3."""
    from cryptography.fernet import Fernet

    from integrations import services as api_services

    api_services.create_client(
        name="加密客户端", scopes=["tournaments:read"], allowed_includes=[]
    )
    archive = make_backup(backups, settings, tmp_path)

    # Swap in a different key, as a careless restore on a new host would.
    # core.crypto builds a Fernet per call, so nothing is cached.
    monkeypatch.setattr(
        settings, "FIELD_ENCRYPTION_KEY", Fernet.generate_key().decode()
    )

    with pytest.raises(CommandError, match="FIELD_ENCRYPTION_KEY"):
        run("restore", str(archive), "--yes")


@pytest.mark.django_db(transaction=True)
def test_restore_accepts_the_matching_key(backups, settings, tmp_path):
    from integrations import services as api_services

    api_services.create_client(
        name="加密客户端", scopes=["tournaments:read"], allowed_includes=[]
    )
    archive = make_backup(backups, settings, tmp_path)

    output = run("restore", str(archive))

    assert "FIELD_ENCRYPTION_KEY 校验通过" in output


@pytest.mark.django_db
def test_restore_lists_what_it_would_do(backups, settings, tmp_path):
    archive = make_backup(backups, settings, tmp_path)

    output = run("restore", str(archive))

    assert "删除 WAL 文件" in output
    assert "清空" in output
    assert "恢复 media" in output


@pytest.mark.django_db
def test_restore_needs_a_real_file():
    with pytest.raises(CommandError, match="找不到备份文件"):
        run("restore", "/nowhere/nothing.tar.gz")


# --- cleanup_static ------------------------------------------------------------


def write_manifest(root, mapping):
    (root / "staticfiles.json").write_text(
        json.dumps({"version": "1.1", "paths": mapping})
    )


def age(path, days):
    old = time.time() - days * 86400
    import os

    os.utime(path, (old, old))


@pytest.mark.django_db
def test_cleanup_static_keeps_everything_the_manifest_names(settings, tmp_path):
    root = tmp_path / "staticfiles"
    root.mkdir()
    settings.STATIC_ROOT = root
    current = root / "css" / "app.abc123.css"
    current.parent.mkdir()
    current.write_text("current")
    age(current, 400)  # old, but still referenced
    write_manifest(root, {"css/app.css": "css/app.abc123.css"})

    output = run("cleanup_static")

    assert current.exists()
    assert "已删除 0 个" in output


@pytest.mark.django_db
def test_cleanup_static_removes_old_unreferenced_files(settings, tmp_path):
    root = tmp_path / "staticfiles"
    (root / "css").mkdir(parents=True)
    settings.STATIC_ROOT = root
    current = root / "css" / "app.new.css"
    current.write_text("current")
    stale = root / "css" / "app.old.css"
    stale.write_text("previous build")
    age(stale, 40)
    recent = root / "css" / "app.recent.css"
    recent.write_text("last week's build")
    age(recent, 5)
    write_manifest(root, {"css/app.css": "css/app.new.css"})

    output = run("cleanup_static")

    assert current.exists()
    assert recent.exists()  # unreferenced but inside the window
    assert not stale.exists()
    assert "已删除 1 个" in output


@pytest.mark.django_db
def test_cleanup_static_does_nothing_without_a_manifest(settings, tmp_path):
    root = tmp_path / "staticfiles"
    (root / "css").mkdir(parents=True)
    settings.STATIC_ROOT = root
    orphan = root / "css" / "whatever.css"
    orphan.write_text("no manifest to check against")
    age(orphan, 400)

    output = run("cleanup_static")

    assert orphan.exists()
    assert "什么都不删" in output


@pytest.mark.django_db
def test_cleanup_static_dry_run(settings, tmp_path):
    root = tmp_path / "staticfiles"
    (root / "css").mkdir(parents=True)
    settings.STATIC_ROOT = root
    stale = root / "css" / "app.old.css"
    stale.write_text("previous build")
    age(stale, 40)
    write_manifest(root, {"css/app.css": "css/app.new.css"})

    output = run("cleanup_static", "--dry-run")

    assert stale.exists()
    assert "将删除 1 个" in output


@pytest.mark.django_db
def test_cleanup_static_keeps_the_manifest_itself(settings, tmp_path):
    root = tmp_path / "staticfiles"
    root.mkdir()
    settings.STATIC_ROOT = root
    write_manifest(root, {"css/app.css": "css/app.new.css"})
    age(root / "staticfiles.json", 400)

    run("cleanup_static")

    assert (root / "staticfiles.json").exists()


# --- optimize_db ---------------------------------------------------------------


@pytest.mark.django_db
def test_optimize_db_runs_and_reports_sizes():
    output = run("optimize_db")

    assert "优化前" in output
    assert "优化后" in output
    assert "MB" in output


@pytest.mark.django_db(transaction=True)
def test_restore_replaces_the_database_and_clears_prerendered(
    backups, settings, tmp_path
):
    """The whole point of the drill: data from the backup comes back."""
    from accounts.models import User

    now = timezone.now()
    User.objects.create_user(
        email="in-the-backup@example.com",
        password="Correct-Horse-Battery-1",
        nickname="备份里的人",
        agreed_terms_at=now,
        agreed_cross_border_at=now,
    )
    archive = make_backup(backups, settings, tmp_path)

    User.objects.filter(email="in-the-backup@example.com").delete()
    assert not User.objects.filter(email="in-the-backup@example.com").exists()

    prerendered = tmp_path / "prerendered"
    (prerendered / "news").mkdir(parents=True)
    (prerendered / "news" / "index.html").write_text("page from before the restore")
    settings.PRERENDER_ROOT = prerendered

    run("restore", str(archive), "--yes")

    assert User.objects.filter(email="in-the-backup@example.com").exists()
    # Design 16.7 step 4: the static pages must not outlive the data.
    assert list(prerendered.iterdir()) == []


@pytest.mark.django_db(transaction=True)
def test_restore_clears_the_wal_before_writing_the_new_database(
    backups, settings, tmp_path, monkeypatch
):
    """Order matters: a leftover WAL must never be replayed into the new file."""
    from core import dbfile

    archive = make_backup(backups, settings, tmp_path)
    settings.PRERENDER_ROOT = tmp_path / "prerendered"

    database = dbfile.database_path()
    order = []
    real_unlink = Path.unlink
    real_copy = shutil.copy2

    def track_unlink(self, *args, **kwargs):
        if self.name.startswith(database.name) and self.name != database.name:
            order.append(f"unlink:{self.suffix}")
        return real_unlink(self, *args, **kwargs)

    def track_copy(src, dst, *args, **kwargs):
        if Path(dst) == database:
            order.append("copy")
        return real_copy(src, dst, *args, **kwargs)

    monkeypatch.setattr(Path, "unlink", track_unlink)
    monkeypatch.setattr(shutil, "copy2", track_copy)

    run("restore", str(archive), "--yes")

    assert "copy" in order
    assert order.index("copy") == len(order) - 1, order
