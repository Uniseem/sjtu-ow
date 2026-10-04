"""Round 175: the reworded checks still catch a script from another host
(AGENTS.md rule 7). Runs the tests first and stops if they are not green (083).

bash scripts/remote-check.sh run uv run python handoff/rounds/175-flaky-cdn-check/mutate.py
"""

import os
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
PY = sys.executable
ENV = {**os.environ, "PYTHONUTF8": "1"}

SCRIM = "scrims/tests/test_teaming.py::test_the_board_carries_what_the_capacity_rule_needs"
CUP = "tournaments/tests/test_adhoc_teams.py::test_the_board_carries_what_the_script_and_the_view_need"
SORTABLE = "  <script src=\"{% static 'vendor/Sortable.min.js' %}\" defer></script>\n"
CDN_SCRIPT = '  <script src="https://cdn.jsdelivr.net/npm/sortablejs@1/Sortable.min.js" defer></script>\n'
CDN_LINK = '  <link rel="stylesheet" href="//cdn.example.com/split.css">\n'

MUTATIONS = [
    ("split page script from a CDN", "scrims/templates/scrims/admin/split.html", SORTABLE, SORTABLE + CDN_SCRIPT, [SCRIM]),
    ("teams page stylesheet from a CDN", "tournaments/templates/tournaments/admin/teams.html", SORTABLE, SORTABLE + CDN_LINK, [CUP]),
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
