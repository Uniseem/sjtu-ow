"""Round 140: break each new rule once and check its test goes red (AGENTS.md
rule 7). Runs the tests first and stops if they are not green (083).

bash scripts/remote-check.sh run uv run python handoff/rounds/140-team-role-filter/mutate.py
"""

import os
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
PY = sys.executable
ENV = {**os.environ, "PYTHONUTF8": "1"}

T = "teams/tests/test_role_filter.py"


def t(name):
    return f"{T}::{name}"


LACK = t("test_lacking_support_lists_what_a_support_can_join")

MUTATIONS = [
    ("the position is ignored", "teams/services.py",
     "        query = query.filter(_wants(role), members_total__lt=limit or max_members())\n",
     "        pass\n", [LACK]),
    ("teams wanting anyone are left out", "teams/services.py",
     '    return Q(recruiting_roles="") | Q(recruiting_roles__contains=role)\n',
     "    return Q(recruiting_roles__contains=role)\n", [LACK]),
    ("full teams are listed", "teams/services.py",
     "        query = query.filter(_wants(role), members_total__lt=limit or max_members())\n",
     "        query = query.filter(_wants(role))\n", [LACK]),
    ("teams not recruiting are listed", "teams/services.py",
     "    if recruiting_only or role:\n", "    if recruiting_only:\n", [LACK]),
    ("an unknown position filters everything out", "teams/views.py",
     "    if role not in labels:\n        role = \"\"\n", "", [t("test_an_unknown_role_shows_everything")]),
    ("the counts include full teams", "teams/services.py",
     "    open_now = Q(is_recruiting=True, members_total__lt=limit)\n",
     "    open_now = Q(is_recruiting=True)\n", [LACK]),
    ("no word when nobody lacks it", "teams/templates/teams/index.html",
     "    {% elif role %}\n", "    {% elif False %}\n", [t("test_nobody_lacking_says_so")]),
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
