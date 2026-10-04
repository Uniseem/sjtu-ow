"""Round 178: break each new rule once and check its test goes red (AGENTS.md
rule 7). Runs the tests first and stops if they are not green (083).

bash scripts/remote-check.sh run uv run python handoff/rounds/178-stopped-members/mutate.py
"""

import os
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
PY = sys.executable
ENV = {**os.environ, "PYTHONUTF8": "1"}

T = "teams/tests/test_stopped_members.py"


def t(name):
    return f"{T}::{name}"


PAGE = t("test_the_team_page_marks_the_stopped_member")
TOP = t("test_a_stopped_captain_is_said_so_up_top")
MANAGE = t("test_the_captain_sees_whom_to_remove")
APPLY = t("test_nobody_applies_to_a_team_whose_captain_is_stopped")
D = "teams/templates/teams/detail.html"

MUTATIONS = [
    ("no tag on the card", D, '{% if not person.is_active %}<span class="c-tag" data-account-stopped>账号已停用</span>{% endif %}', "", [PAGE, TOP]),
    ("the motto still shown", D, "                      {% if person.is_active %}\n                        {% if person.motto %}", "                      {% if True %}\n                        {% if person.motto %}", [PAGE]),
    ("nothing said up top", D, "{% if not captain.is_active %}（账号已停用）{% endif %}", "", [TOP]),
    ("the captain's page silent", "teams/templates/teams/manage.html", '{% if not membership.user.is_active %} <span class="c-tag ml-1" data-account-stopped>', '{% if False %} <span class="c-tag ml-1" data-account-stopped>', [MANAGE]),
    ("applications still open", "teams/services.py", "    if teams_without_captain().filter(pk=team.pk).exists():\n        return False, CAPTAIN_STOPPED\n", "", [APPLY]),
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
