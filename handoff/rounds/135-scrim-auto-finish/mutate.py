"""Round 135: break each new rule once and check its test goes red (AGENTS.md
rule 7). Runs the tests first and stops if they are not green (083).

bash scripts/remote-check.sh run uv run python handoff/rounds/135-scrim-auto-finish/mutate.py
"""

import os
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
PY = sys.executable
ENV = {**os.environ, "PYTHONUTF8": "1"}

T = "scrims/tests/test_auto_finish.py"


def t(name):
    return f"{T}::{name}"


ARRANGED = t("test_publishing_and_saving_arrange_it")

MUTATIONS = [
    ("publishing arranges nothing", "scrims/services.py",
     "    schedule_reminder(scrim)\n    schedule_auto_finish(scrim)\n    _status_changed(scrim)\n",
     "    schedule_reminder(scrim)\n    _status_changed(scrim)\n", [ARRANGED]),
    ("saving does not follow the new start", "scrims/services.py",
     "        schedule_reminder(scrim)\n        schedule_auto_finish(scrim)\n    _refresh_pages(scrim)\n",
     "        schedule_reminder(scrim)\n    _refresh_pages(scrim)\n", [ARRANGED]),
    ("a draft edit arranges it too", "scrims/services.py",
     "    if scrim.status == ScrimStatus.PUBLISHED:\n        schedule_reminder(scrim)\n        schedule_auto_finish(scrim)\n",
     "    schedule_auto_finish(scrim)\n    if scrim.status == ScrimStatus.PUBLISHED:\n        schedule_reminder(scrim)\n",
     [t("test_a_draft_edit_arranges_nothing")]),
    ("an hour, not six", "scrims/services.py",
     "FINISH_AFTER = timedelta(hours=6)\n", "FINISH_AFTER = timedelta(hours=1)\n",
     [t("test_too_early_or_cancelled_leaves_it_alone")]),
    ("finished early", "scrims/tasks.py",
     "    if timezone.now() < due:\n        # The start moved later",
     "    if False:\n        # The start moved later",
     [t("test_too_early_or_cancelled_leaves_it_alone")]),
    ("cancelled scrims get finished", "scrims/tasks.py",
     '    if scrim.status != ScrimStatus.PUBLISHED:\n        return "not_published"\n    due = services.finish_time(scrim)\n',
     "    due = services.finish_time(scrim)\n",
     [t("test_too_early_or_cancelled_leaves_it_alone")]),
    ("the task never finishes it", "scrims/tasks.py",
     "    services.finish(scrim=scrim)\n", "", [t("test_six_hours_after_the_start_it_is_finished")]),
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
