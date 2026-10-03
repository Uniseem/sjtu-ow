"""Round 149: break each new rule once and check its test goes red (AGENTS.md
rule 7). Runs the tests first and stops if they are not green (083).

bash scripts/remote-check.sh run uv run python handoff/rounds/149-my-teams-contact/mutate.py
"""

import os
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
PY = sys.executable
ENV = {**os.environ, "PYTHONUTF8": "1"}

T = "teams/tests/test_member_contact.py::test_my_teams_lists_how_to_reach_each"
PAGE = "templates/me/teams.html"

MUTATIONS = [
    ("the contact is not shown", PAGE,
     '{% if membership.team.member_contact %}<span class="font-code">', '{% if False %}<span class="font-code">',
     [T]),
    ("no word when the captain has not filled it", PAGE,
     '<span class="text-sm text-fg-3">队长还没填</span>', "", [T]),
    ("the captain is not sent to fill it", PAGE,
     "{% elif membership.is_captain %}<a href=", "{% elif False %}<a href=", [T]),
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
