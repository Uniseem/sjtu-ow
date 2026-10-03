"""Round 131: break each new rule once and check its test goes red (AGENTS.md
rule 7). Runs the tests first and stops if they are not green (083).

bash scripts/remote-check.sh run uv run python handoff/rounds/131-member-left/mutate.py
"""

import os
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
PY = sys.executable
ENV = {**os.environ, "PYTHONUTF8": "1"}

T = "teams/tests/test_member_left.py"
HEARS = f"{T}::test_the_captain_hears_who_left"
NAMED = f"{T}::test_a_live_roster_that_still_lists_them_is_named"
DEAD = f"{T}::test_dead_registrations_are_not_named"

MUTATIONS = [
    ("leaving tells nobody", "teams/services.py",
     "    notifications.member_left(team, user)\n", "", [HEARS]),
    ("rejected rosters are named", "tournaments/registration.py",
     "            members__user=user,\n            members__is_active=True,\n",
     "            members__user=user,\n", [DEAD]),
    ("finished tournaments are named", "tournaments/registration.py",
     "            tournament__status__in=(\n                TournamentStatus.DRAFT,\n"
     "                TournamentStatus.PUBLISHED,\n            ),\n", "", [DEAD]),
    ("the letter leaves out the roster", "teams/notifications.py",
     "    if entries:\n        from tournaments.notifications import moment\n",
     "    if False:\n        from tournaments.notifications import moment\n", [NAMED]),
    ("the letter points to the team, not the entry", "teams/notifications.py",
     '        action = ("查看报名详情", site_url(entries[0].get_absolute_url()))\n', "",
     [NAMED]),
    ("no specimen", "core/email_samples.py",
     '            "member-left",\n', '            "member-left-gone",\n',
     [f"{T}::test_the_letter_is_on_the_specimen_page"]),
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
