"""Round 156: break each new rule once and check its test goes red (AGENTS.md
rule 7). Runs the tests first and stops if they are not green (083).

bash scripts/remote-check.sh run uv run python handoff/rounds/156-my-agenda/mutate.py
"""

import os
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
PY = sys.executable
ENV = {**os.environ, "PYTHONUTF8": "1"}

T = "core/tests/test_agenda.py"
MINE = f"{T}::test_my_signups_in_time_order"
PAST = f"{T}::test_past_cancelled_and_strangers_see_nothing"
GONE = f"{T}::test_a_cancelled_tournament_leaves_the_list"
A = "core/agenda.py"

MUTATIONS = [
    ("old scrims stay", A, "            scrim__starts_at__gte=now - SCRIM_GRACE,\n", "", [PAST]),
    ("cancelled scrims stay", A, "            scrim__status=ScrimStatus.PUBLISHED,\n", "", [PAST]),
    ("no scrims", A, "    for signup in signups:\n        place =", "    for signup in signups[:0]:\n        place =", [MINE]),
    ("no rosters", A, "        if upcoming(row.tournament):\n", "        if False:\n", [MINE]),
    ("cancelled tournaments stay", A,
     "        is_active=True,\n        tournament__status=TournamentStatus.PUBLISHED,\n",
     "        is_active=True,\n", [GONE]),
    ("no pool signups", A, "        if upcoming(signup.tournament):\n", "        if False:\n", [MINE]),
    ("undated first", A,
     "    items.sort(key=lambda item: (item.when is None, item.when or now))\n",
     "    items.sort(key=lambda item: (item.when is not None, item.when or now))\n", [MINE]),
    ("not on the homepage", "content/templates/content/home_page.html",
     '    {% include "slots/agenda.html" %}\n', "", [MINE]),
    ("no slot to fetch", "core/apps.py", '        register("my-agenda", my_agenda_slot)\n', "", [MINE]),
    ("strangers get the panel", "templates/slots/agenda.html",
     "  {% if request.user.is_authenticated %}\n", "  {% if True %}\n", [PAST]),
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
