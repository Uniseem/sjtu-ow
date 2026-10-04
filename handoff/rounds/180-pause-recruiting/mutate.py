"""Round 180: break each new rule once and check its test goes red (AGENTS.md
rule 7). Runs the tests first and stops if they are not green (083).

bash scripts/remote-check.sh run uv run python handoff/rounds/180-pause-recruiting/mutate.py
"""

import os
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
PY = sys.executable
ENV = {**os.environ, "PYTHONUTF8": "1"}

T = "teams/tests/test_pause_recruiting.py"


def t(name):
    return f"{T}::{name}"


ONLY = t("test_only_the_teams_they_captain_and_recruit_for_are_paused")
FILTERS = t("test_the_recruiting_filters_no_longer_list_it")
QUIET = t("test_nothing_to_redo_when_nothing_recruits")
TOLD = t("test_the_admin_is_told_the_teams_were_paused")
TS = "teams/services.py"

MUTATIONS = [
    ("nothing paused on stopping", "accounts/services.py", "    return pause_recruiting(user)\n", "    return []\n", [ONLY, FILTERS, TOLD]),
    ("quiet teams counted too", TS, "    paused = [team for team in captained_teams(user) if team.is_recruiting]\n", "    paused = captained_teams(user)\n", [ONLY]),
    ("flag left on", TS, "        team.is_recruiting = False\n        team.save(", "        team.is_recruiting = True\n        team.save(", [ONLY, FILTERS]),
    ("team page not redone", TS, '''        team.save(update_fields=["is_recruiting", "updated_at"])
        prerender.request_page(team.get_absolute_url(), kind="team")
''', '''        team.save(update_fields=["is_recruiting", "updated_at"])
''', [ONLY]),
    ("list not redone", TS, "    if paused:\n        refresh_team_list()\n", "", [ONLY]),
    ("list redone for nothing", TS, "    if paused:\n        refresh_team_list()\n", "    if True:\n        refresh_team_list()\n", [QUIET]),
    ("admin not told", "accounts/admin_users.py", "            if paused:\n", "            if False:\n", [TOLD]),
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
