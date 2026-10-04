"""Round 158: break each new rule once and check its test goes red (AGENTS.md
rule 7). Runs the tests first and stops if they are not green (083).

bash scripts/remote-check.sh run uv run python handoff/rounds/158-scheduled-publishing/mutate.py
"""

import os
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
PY = sys.executable
ENV = {**os.environ, "PYTHONUTF8": "1"}

T = "content/tests/test_scheduled_publishing.py"


def t(name):
    return f"{T}::{name}"


LIVE = t("test_a_scheduled_article_goes_live_when_its_time_comes")
EXPIRE = t("test_an_article_comes_down_when_it_expires")
S = "content/services.py"
W = "core/worker.py"

MUTATIONS = [
    ("never runs the command", S, '        call_command("publish_scheduled", stdout=StringIO())', "        pass", [LIVE, EXPIRE]),
    ("runs it every time", S, "    if due:\n        call_command", "    if True:\n        call_command", [LIVE]),
    ("go-live times not looked at", S, "        Revision.objects.filter(approved_go_live_at__lt=now).exists()\n        or ", "        ", [LIVE]),
    ("expiry not looked at", S, "\n        or Page.objects.filter(live=True, expire_at__lt=now).exists()", "", [EXPIRE]),
    ("the worker does not call it", W, "        try:\n            publish_due_pages()\n", "        try:\n            pass\n", [t("test_the_worker_does_it_on_every_beat")]),
    ("a failure kills the loop", W, '        except Exception:\n            logger.exception("Failed to publish scheduled pages")\n', "        except ZeroDivisionError:\n            pass\n", [t("test_a_failure_does_not_stop_the_heartbeat")]),
    ("the manual sends editors nowhere", "core/admin_manual.py", "编辑页右侧「状态」面板点「设置计划」", "编辑页里", [t("test_the_admin_manual_says_where_the_schedule_is")]),
    ("authors told the old place", "core/admin_manual.py", "定时发布在右侧「状态」面板的「设置计划」里", "定时发布也在那里", [t("test_the_admin_manual_says_where_the_schedule_is")]),
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
