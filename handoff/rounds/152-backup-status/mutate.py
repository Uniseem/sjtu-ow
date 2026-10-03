"""Round 152: break each new rule once and check its test goes red (AGENTS.md
rule 7). Runs the tests first and stops if they are not green (083).

bash scripts/remote-check.sh run uv run python handoff/rounds/152-backup-status/mutate.py
"""

import os
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
PY = sys.executable
ENV = {**os.environ, "PYTHONUTF8": "1"}

TODO = "core/tests/test_admin_functions.py::test_the_owner_hears_about_missing_or_failed_backups"
RUN = "core/tests/test_offsite_backup.py::test_each_run_leaves_a_status"
CMD = "core/management/commands/backup.py"

MUTATIONS = [
    ("a failed upload leaves no status", CMD,
     '            write_status(root, archive, "failed", str(exc))\n', "", [RUN]),
    ("a good run leaves no status", CMD,
     "        write_status(root, archive, offsite_result)\n", "", [RUN]),
    ("skipped reads as uploaded", CMD,
     '            return "skipped"\n', '            return "uploaded"\n', [RUN]),
    ("no word without backups", "core/admin_todo.py",
     '        problems.append("还没有任何备份，每天夜里的备份定时任务可能没设好")\n', "        pass\n",
     [TODO]),
    ("old backups look fine", "core/admin_todo.py",
     "        if age > BACKUP_STALE:\n", "        if False:\n", [TODO]),
    ("fresh backups look stale", "core/admin_todo.py",
     "        if age > BACKUP_STALE:\n", "        if True:\n", [TODO]),
    ("a failed upload is not mentioned", "core/admin_todo.py",
     '    if status.get("offsite") == "failed":\n', "    if False:\n", [TODO]),
    ("the panel drops rows without a link", "core/templates/core/admin/todo_panel.html",
     "{% else %}{{ row.text }}{% endif %}", "{% endif %}", [TODO]),
]


def run(tests):
    return subprocess.run(
        [PY, "-m", "pytest", "-q", "-x", "-p", "no:cacheprovider", *tests],
        cwd=ROOT, env=ENV, capture_output=True, text=True,
    ).returncode


def main():
    every = sorted({t for *_rest, tests in MUTATIONS for t in tests})
    assert run(every) == 0, "baseline is red"
    print("baseline green,", len(every), "tests")
    failed = []
    for label, rel, old, new, tests in MUTATIONS:
        path = ROOT / rel
        backup = path.with_suffix(path.suffix + ".mutbak")
        shutil.copy2(path, backup)
        try:
            raw = path.read_bytes().decode("utf-8")
            crlf = "\r\n" in raw
            text = raw.replace("\r\n", "\n")
            assert text.count(old) == 1, (label, text.count(old))
            text = text.replace(old, new)
            path.write_bytes((text.replace("\n", "\r\n") if crlf else text).encode("utf-8"))
            for test in tests:
                red = run([test]) != 0
                print(("caught " if red else "MISSED ") + label + " -> " + test.split("::")[1])
                if not red:
                    failed.append((label, test))
        finally:
            shutil.copy2(backup, path)
            backup.unlink()
            folder = rel.rsplit("/", 1)[0]
            for cache in ROOT.glob(folder + "/__pycache__/*.pyc"):
                cache.unlink()
    assert run(every) == 0, "not green after restoring"
    print("restored and green;", "missed:", failed or "none")
    return 1 if failed else 0


sys.exit(main())
