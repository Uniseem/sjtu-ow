"""Round 126: break each new rule once and check its test goes red (AGENTS.md
rule 7). Runs the tests first and stops if they are not green (083).

uv run python handoff/rounds/126-my-placement/mutate.py
"""

import os
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
PY = sys.executable
ENV = {**os.environ, "PYTHONUTF8": "1"}

T = "scrims/tests/test_my_placement.py"


def t(name):
    return f"{T}::{name}"


MUTATIONS = [
    ("a place before any split", "scrims/services.py",
     "    if not has_split:\n        return \"\"\n", "",
     [t("test_the_wording_for_each_place"), t("test_my_scrims_lists_my_place")]),
    ("open formats name a role", "scrims/services.py",
     "        if scrim.role_queue and signup.assigned_role:\n", "        if signup.assigned_role:\n",
     [t("test_the_wording_for_each_place")]),
    ("the bench reads as left out", "scrims/services.py",
     "    if signup.is_selected:\n        return \"替补\"\n", "",
     [t("test_the_wording_for_each_place")]),
    ("the scrim page hides my place", "scrims/slots.py",
     '        "my_placement": services.placement(my_signup) if my_signup else "",\n',
     '        "my_placement": "",\n',
     [t("test_the_scrim_page_shows_only_my_place")]),
    ("my scrims shows no place", "scrims/views.py",
     "        signup.placement = services.placement(\n",
     "        signup.placement = \"\" and services.placement(\n",
     [t("test_my_scrims_lists_my_place")]),
    ("the reminder leaves out the place", "scrims/notifications.py",
     '        facts = [*facts, ("你的分队", f"{placement}（以群里发的为准）")]\n', "        pass\n",
     [t("test_the_reminder_tells_each_player_their_place")]),
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
