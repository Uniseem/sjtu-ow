"""Round 141: break each new rule once and check its test goes red (AGENTS.md
rule 7). Runs the tests first and stops if they are not green (083).

bash scripts/remote-check.sh run uv run python handoff/rounds/141-stale-applications/mutate.py
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


CLOSES = t("test_two_weeks_unanswered_closes_and_tells_the_applicant")
CMD = "core/management/commands/cleanup_old_data.py"

MUTATIONS = [
    ("closed after twelve days", "teams/services.py",
     "STALE_APPLICATION_DAYS = 14\n", "STALE_APPLICATION_DAYS = 12\n", [CLOSES]),
    ("answered ones are closed too", "teams/services.py",
     "        status=ApplicationStatus.PENDING, created_at__lt=cutoff\n",
     "        created_at__lt=cutoff\n", [t("test_answered_ones_are_left_alone")]),
    ("nobody is told", "teams/services.py",
     "        notifications.application_expired(application)\n", "", [CLOSES]),
    ("no reason recorded", "teams/services.py",
     "        application.decision_note = STALE_NOTE\n", "", [CLOSES]),
    ("the nightly job skips it", CMD,
     "        closed = self.stale_applications(dry_run, now)\n", "        closed = 0\n",
     [CLOSES]),
    ("a dry run closes them", CMD,
     "        if dry_run:\n            return services.stale_applications(now).count()\n", "",
     [t("test_a_dry_run_only_counts")]),
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
