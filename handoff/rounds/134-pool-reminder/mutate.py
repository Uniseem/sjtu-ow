"""Round 134: break each new rule once and check its test goes red (AGENTS.md
rule 7). Runs the tests first and stops if they are not green (083).

bash scripts/remote-check.sh run uv run python handoff/rounds/134-pool-reminder/mutate.py
"""

import os
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
PY = sys.executable
ENV = {**os.environ, "PYTHONUTF8": "1"}

T = "tournaments/tests/test_reminder.py"


def t(name):
    return f"{T}::{name}"


HEARS = t("test_the_pool_hears_once_teams_are_being_formed")
NO_TEAMS = t("test_no_teams_yet_no_pool_letters")

MUTATIONS = [
    ("the pool hears nothing", "tournaments/tasks.py",
     "    pool = notifications.unplaced_reminder(tournament)\n", "    pool = 0\n", [HEARS]),
    ("the pool hears before any team exists", "tournaments/tasks.py",
     '    if not sent:\n        return "sent:0"\n    pool = notifications.unplaced_reminder(tournament)\n',
     '    pool = notifications.unplaced_reminder(tournament)\n    if not sent:\n        return "sent:0"\n',
     [NO_TEAMS]),
    ("placed players get the pool letter too", "tournaments/notifications.py",
     "    for signup in tournament.individual_signups.filter(\n        registration__isnull=True\n    ).select_related(\"user\"):\n",
     "    for signup in tournament.individual_signups.select_related(\"user\"):\n", [HEARS]),
    ("deactivated pool signups hear too", "tournaments/notifications.py",
     "        if not (signup.user.is_active and signup.user.email):\n",
     "        if not signup.user.email:\n", [t("test_a_deactivated_pool_signup_is_skipped")]),
    ("being placed says nothing about when", "tournaments/notifications_registration.py",
     '        facts.append(("比赛时间", moment(registration.tournament.starts_at)))\n',
     "        pass\n", [t("test_being_placed_says_when")]),
    ("no specimen", "core/email_samples.py",
     '            "unplaced-reminder",\n', '            "unplaced-reminder-gone",\n',
     [t("test_the_pool_letter_is_on_the_specimen_page")]),
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
