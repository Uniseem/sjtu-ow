"""Round 145: break each new rule once and check its test goes red (AGENTS.md
rule 7). Runs the tests first and stops if they are not green (083).

bash scripts/remote-check.sh run uv run python handoff/rounds/145-captain-reminder/mutate.py
"""

import os
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
PY = sys.executable
ENV = {**os.environ, "PYTHONUTF8": "1"}

T = "teams/tests/test_stale_applications.py"


def t(name):
    return f"{T}::{name}"


ONCE = t("test_a_week_in_the_captain_hears_once")

MUTATIONS = [
    ("the nightly job does not remind", "core/management/commands/cleanup_old_data.py",
     "        reminded = 0 if dry_run else self.remind_captains(now)\n", "        reminded = 0\n",
     [ONCE]),
    ("reminded after three days", "teams/services.py",
     "REMIND_CAPTAIN_DAYS = 7\n", "REMIND_CAPTAIN_DAYS = 2\n", [ONCE]),
    ("reminded every night", "teams/services.py",
     "            captain_reminded_at__isnull=True,\n", "", [ONCE]),
    ("nothing marked as reminded", "teams/services.py",
     "        TeamApplication.objects.filter(pk__in=[a.pk for a in applications]).update(\n            captain_reminded_at=now\n        )\n",
     "", [ONCE]),
    ("one letter per application", "teams/services.py",
     "        by_team.setdefault(application.team_id, []).append(application)\n",
     "        by_team.setdefault(application.pk, []).append(application)\n", [ONCE]),
    ("no word about closing", "teams/notifications.py",
     '            f"{REMIND_CAPTAIN_DAYS} 天以上，再过 {left} 天没处理会自动关闭。"\n',
     '            f"{REMIND_CAPTAIN_DAYS} 天以上。"\n', [ONCE]),
    ("no specimen", "core/email_samples.py",
     '            "applications-waiting",\n', '            "applications-waiting-gone",\n',
     [t("test_the_reminder_is_on_the_specimen_page")]),
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
