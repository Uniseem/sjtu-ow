"""217 复核 09（运维、邮件、信）的复现。每条测试断言的是「缺陷存在时的样子」，
所以 passed = 已复现。只读业务代码，不改任何东西。

跑法（测试机）：
    bash scripts/remote-check.sh run uv run pytest -q -p no:cacheprovider \
        handoff/rounds/217-second-review/findings/09-repro.py
"""

import os
import tarfile
import tempfile
import time
from datetime import timedelta
from io import StringIO
from pathlib import Path
from unittest import mock

import pytest
from django.core.management import call_command
from django.utils import timezone

# Fixtures reused from the project's own tests (imported names are collected).
from core.tests.test_announcements import _member, _planned, site, worker  # noqa: F401
from core.tests.test_offsite_backup import bucket, configured  # noqa: F401


def run(*args):
    out = StringIO()
    call_command(*args, stdout=out, stderr=out)
    return out.getvalue()


# --- 09-1: a failed backup leaves a half-written archive that hides the failure ---


@pytest.mark.django_db
def test_09_1_failed_backup_leaves_partial_archive_and_todo_stays_quiet(
    settings, tmp_path, monkeypatch
):
    from core.admin_todo import backup_problems
    from core.management.commands import backup as backup_command

    root = tmp_path / "backups"
    root.mkdir()
    settings.BACKUP_ROOT = root
    settings.MEDIA_ROOT = tmp_path / "media"
    settings.MEDIA_ROOT.mkdir()
    (settings.MEDIA_ROOT / "a.png").write_bytes(b"x" * 4096)

    # A good backup from two days ago.
    run("backup")
    (good,) = root.glob("sjtu-ow-*.tar.gz")
    two_days = timezone.localtime() - timedelta(days=2)
    older = root / f"sjtu-ow-{two_days:%Y%m%d-%H%M%S}.tar.gz"
    good.rename(older)
    stamp = time.time() - 48 * 3600
    os.utime(older, (stamp, stamp))
    status = backup_command.read_status(root)
    status_archive_before = status["archive"]
    before = backup_problems()
    print("todo before the failing run:", before)
    assert before and "小时前" in before[0]  # 48 h > 36 h: the to-do speaks up

    # Tonight's run: a media file disappears while tar walks the folder.
    original_add = tarfile.TarFile.add

    def flaky(self, name, arcname=None, recursive=True, *, filter=None):  # noqa: A002
        if arcname == "media/a.png":
            raise FileNotFoundError(name)
        return original_add(self, name, arcname, recursive, filter=filter)

    monkeypatch.setattr(tarfile.TarFile, "add", flaky)
    with pytest.raises(FileNotFoundError):
        run("backup")
    monkeypatch.setattr(tarfile.TarFile, "add", original_add)

    archives = sorted(root.glob("sjtu-ow-*.tar.gz"))
    partial = archives[-1]
    print("archives after the failing run:", [p.name for p in archives])
    assert partial != older and partial.stat().st_size > 0

    after = backup_problems()
    print("todo after the failing run:", after)
    assert after == []  # the to-do now says nothing is wrong

    # The status file still describes the run two days ago.
    assert backup_command.read_status(root)["archive"] == status_archive_before

    # And the archive it is counting on cannot be restored.
    with pytest.raises((EOFError, tarfile.ReadError)):
        with tarfile.open(partial, "r:gz") as bundle:
            bundle.getmembers()


# --- 09-2: a tournament draft with only a summary is deleted as "empty" ------------


@pytest.mark.django_db
def test_09_2_tournament_draft_with_summary_is_deleted_by_cleanup(site, client):  # noqa: F811
    from core.tests.test_autosave_events import AUTOSAVE
    from django.urls import reverse

    from tournaments.models import Tournament, TournamentStatus

    manager = _member("tm217@example.com", "赛事管理员")
    client.force_login(manager)
    client.post(
        reverse("tournaments:add"),
        {"summary": "春季赛的简介，写了一大段", "participant_contact": "QQ 群 123"},
        **AUTOSAVE,
    )
    draft = Tournament.objects.get(status=TournamentStatus.DRAFT)
    print("draft:", repr(draft.title), repr(draft.summary), repr(draft.participant_contact))
    assert draft.title == "" and draft.summary.startswith("春季赛")
    Tournament.objects.filter(pk=draft.pk).update(
        updated_at=timezone.now() - timedelta(days=8)
    )

    output = run("cleanup_old_data")
    print(output)

    assert not Tournament.objects.filter(pk=draft.pk).exists()


# --- 09-3: the 30-minute gap does not hold after a planned article goes live ------


@pytest.mark.django_db
def test_09_3_gap_bypassed_right_after_a_planned_article_goes_live(
    site,  # noqa: F811
    worker,  # noqa: F811
    mailoutbox,
    django_capture_on_commit_callbacks,
):
    from content.models import ArticlePage
    from content.services import publish_due_pages
    from core import services
    from core.models import Broadcast

    editor = _member("editor217@example.com", "内容编辑")
    _member("reader217@example.com")
    go_live_at = timezone.now() + timedelta(hours=3)
    page = _planned(editor, go_live_at)
    with django_capture_on_commit_callbacks(execute=True):
        services.announce(kind="article", obj=page, actor=editor)
    assert mailoutbox == []

    later = go_live_at + timedelta(seconds=30)
    with mock.patch("django.utils.timezone.now", return_value=later):
        with django_capture_on_commit_callbacks(execute=True):
            assert publish_due_pages()
        first_wave = len(mailoutbox)
        print("letters when it went live:", first_wave)
        assert first_wave >= 2

        page = ArticlePage.objects.get(pk=page.pk)
        problem = services.announcement_problem("article", page)
        print("announcement_problem 30 s after the planned mail went out:", repr(problem))
        assert problem == ""
        with django_capture_on_commit_callbacks(execute=True):
            services.announce(kind="article", obj=page, actor=editor)
        print("letters after a second click:", len(mailoutbox))
        assert len(mailoutbox) == 2 * first_wave
        assert Broadcast.objects.filter(kind="article", object_id=page.pk).count() == 2


# --- 09-4: /healthz counts a delayed task one second overdue as a 10-minute backlog -


@pytest.mark.django_db
def test_09_4_delayed_task_one_second_overdue_fails_the_backlog_check():
    from django_tasks.base import TaskResultStatus
    from django_tasks_db.models import DBTaskResult

    from core.health import check_task_backlog

    now = timezone.now()
    row = DBTaskResult.objects.create(
        args_kwargs={"args": [1], "kwargs": {}},
        task_path="scrims.tasks.send_scrim_reminder",
        backend_name="default",
        queue_name="default",
        run_after=now - timedelta(seconds=1),  # due one second ago
        status=TaskResultStatus.READY,
    )
    # Arranged two days ago, when the scrim was saved.
    DBTaskResult.objects.filter(pk=row.pk).update(enqueued_at=now - timedelta(days=2))

    ok, detail = check_task_backlog()
    print("check_task_backlog:", ok, detail)
    assert ok is False


# --- 09-5: restore --from-s3 leaves the decrypted archive in /tmp -----------------


@pytest.mark.django_db
def test_09_5_restore_from_s3_leaves_the_decrypted_backup_behind(
    tmp_path,
    settings,
    bucket,  # noqa: F811
    configured,  # noqa: F811
    monkeypatch,
):
    settings.MEDIA_ROOT = tmp_path / "media"
    settings.MEDIA_ROOT.mkdir()
    run("backup", "--output", str(tmp_path / "backups"))
    _bucket_name, key = bucket.uploads[0]

    scratch = tmp_path / "tmp"
    scratch.mkdir()
    monkeypatch.setattr(tempfile, "tempdir", str(scratch))

    output = run("restore", "--from-s3", key)  # dry run: changes nothing
    print(output)

    left = list(scratch.glob("restore-*/downloaded.tar.gz"))
    print("left behind:", left)
    assert left
    with tarfile.open(left[0], "r:gz") as bundle:
        names = bundle.getnames()
    print("members:", names)
    assert "db.sqlite3" in names  # plaintext database, users' emails included
    assert Path(left[0]).stat().st_size > 0
