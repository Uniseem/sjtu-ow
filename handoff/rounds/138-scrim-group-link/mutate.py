"""Round 138: break each new rule once and check its test goes red (AGENTS.md
rule 7). Runs the tests first and stops if they are not green (083).

bash scripts/remote-check.sh run uv run python handoff/rounds/138-scrim-group-link/mutate.py
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


TOLD = t("test_signed_up_players_are_told_which_group")
REMINDER = t("test_the_reminder_links_the_group")

MUTATIONS = [
    ("the slot gets no link", "scrims/slots.py",
     '        "group_url": services.community_group_url() if my_signup else "",\n',
     '        "group_url": "",\n', [TOLD]),
    ("the slot leaves it out", "scrims/templates/scrims/slots/actions.html",
     "      {% if group_url %}<p", "      {% if False %}<p", [TOLD]),
    ("said even with no link", "scrims/templates/scrims/slots/actions.html",
     "      {% if group_url %}<p", "      {% if True %}<p",
     [t("test_no_group_link_set_nothing_said")]),
    ("the reminder leaves it out", "scrims/notifications.py",
     '        facts = [*facts, ("社团 QQ 群", group_url)]\n', "        pass\n", [REMINDER]),
    ("the reminder is not given the link", "scrims/notifications.py",
     "            scrim, placement(signup, has_split=has_split), group_url\n",
     "            scrim, placement(signup, has_split=has_split)\n", [REMINDER]),
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
