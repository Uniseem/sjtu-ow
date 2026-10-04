"""Round 174: break each new rule once and check its test goes red (AGENTS.md
rule 7). Runs the tests first and stops if they are not green (083).

bash scripts/remote-check.sh run uv run python handoff/rounds/174-user-bulk-actions/mutate.py
"""

import os
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
PY = sys.executable
ENV = {**os.environ, "PYTHONUTF8": "1"}

T = "accounts/tests/test_user_bulk_actions.py"


def t(name):
    return f"{T}::{name}"


SHOWN = t("test_only_assigning_roles_is_left")
DONE = t("test_the_addresses_do_nothing")
H = "accounts/wagtail_hooks.py"

MUTATIONS = [
    ("bulk delete back", H, 'USER_BULK_ACTIONS_OFF = ("delete", "set_active_state")', 'USER_BULK_ACTIONS_OFF = ("set_active_state",)', [SHOWN, DONE]),
    ("bulk switch-off back", H, 'USER_BULK_ACTIONS_OFF = ("delete", "set_active_state")', 'USER_BULK_ACTIONS_OFF = ("delete",)', [SHOWN]),
    ("the registry left alone", H, "bulk_action_registry._scan_for_bulk_actions = _without_user_bulk_actions(\n    bulk_action_registry._scan_for_bulk_actions\n)\n", "", [SHOWN, DONE]),
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
