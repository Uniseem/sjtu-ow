"""Round 177: break each new rule once and check its test goes red (AGENTS.md
rule 7). Runs the tests first and stops if they are not green (083).

bash scripts/remote-check.sh run uv run python handoff/rounds/177-captainless-teams/mutate.py
"""

import os
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
PY = sys.executable
ENV = {**os.environ, "PYTHONUTF8": "1"}

T = "teams/tests/test_captainless.py"


def t(name):
    return f"{T}::{name}"


WHICH = t("test_which_teams_have_no_working_captain")
TOLD = t("test_the_owner_is_told_and_sent_where_to_fix_it")
SAID = t("test_stopping_a_captain_says_which_teams")
TS = "teams/services.py"

MUTATIONS = [
    ("disabled captains still count", TS, "        role=TeamRole.CAPTAIN, user__is_active=True\n", "        role=TeamRole.CAPTAIN\n", [WHICH, TOLD]),
    ("disbanded teams too", TS, "    return Team.objects.filter(disbanded_at__isnull=True).exclude(pk__in=working)\n", "    return Team.objects.exclude(pk__in=working)\n", [WHICH]),
    ("always the whole list", "core/admin_todo.py", "            if count == 1\n", "            if False\n", [TOLD]),
    ("no to-do row", "core/admin_todo.py", "    if stuck:\n        count = teams_without_captain().count()\n", "    if False:\n        count = teams_without_captain().count()\n", [TOLD]),
    ("the list not filtered", "teams/wagtail_hooks.py", '        if self.request.GET.get("captain") == "gone":\n', "        if False:\n", [TOLD]),
    ("the edit page says nothing", "accounts/admin_users.py", "            if teams:\n", "            if False:\n", [SAID]),
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
