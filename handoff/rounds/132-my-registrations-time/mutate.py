"""Round 132: break each new rule once and check its test goes red (AGENTS.md
rule 7). Runs the tests first and stops if they are not green (083).

bash scripts/remote-check.sh run uv run python handoff/rounds/132-my-registrations-time/mutate.py
"""

import os
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
PY = sys.executable
ENV = {**os.environ, "PYTHONUTF8": "1"}

T = "tournaments/tests/test_my_registrations.py"
TEAM = f"{T}::test_team_entries_show_the_start"
SOLO = f"{T}::test_individual_entries_show_the_start"
PAGE = "templates/me/registrations.html"
CELL = (
    '              <td data-label="比赛时间" class="font-numeric" data-starts>'
    '{% include "tournaments/_starts_at.html" with tournament={who}.tournament %}</td>\n'
)

MUTATIONS = [
    ("team entries without the time", PAGE, CELL.replace("{who}", "registration"), "",
     [TEAM]),
    ("individual entries without the time", PAGE, CELL.replace("{who}", "signup"), "",
     [SOLO]),
    ("only the date", "tournaments/templates/tournaments/_starts_at.html",
     " {{ tournament.starts_at|ow_time }}", "", [TEAM, SOLO]),
    ("the registration page leaves out the time",
     "tournaments/templates/tournaments/registration_detail.html",
     "        {% if registration.tournament.starts_at %}<span", "        {% if False %}<span",
     [f"{T}::test_the_registration_page_says_when"]),
    ("no 未定", "tournaments/templates/tournaments/_starts_at.html",
     '<span class="text-fg-3">未定</span>', "", [TEAM]),
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
