"""Round 147: break each new rule once and check its test goes red (AGENTS.md
rule 7). Runs the tests first and stops if they are not green (083).

bash scripts/remote-check.sh run uv run python handoff/rounds/147-member-filter/mutate.py
"""

import os
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
PY = sys.executable
ENV = {**os.environ, "PYTHONUTF8": "1"}

T = "members/tests/test_member_filter.py"


def t(name):
    return f"{T}::{name}"


ROLE = t("test_by_usual_position")
FREE = t("test_only_people_without_a_team")
REST = t("test_no_filter_lists_everyone_and_nobody_matching_says_so")
PAGE = "members/templates/members/index.html"

MUTATIONS = [
    ("the position is ignored", "members/services.py",
     "        if (not role or member.user.main_role == role) and not (free and member.teams)\n",
     "        if not (free and member.teams)\n", [ROLE]),
    ("people in teams stay", "members/services.py",
     "        if (not role or member.user.main_role == role) and not (free and member.teams)\n",
     "        if (not role or member.user.main_role == role)\n", [FREE]),
    ("numbers start again at 001", PAGE,
     "{{ member.number|stringformat:\"03d\" }}", "{{ forloop.counter|stringformat:\"03d\" }}",
     [ROLE]),
    ("groups shown while filtering", PAGE,
     "      {% if not filtering %}{% for section in sections %}", "      {% if True %}{% for section in sections %}",
     [ROLE]),
    ("an unknown position filters everyone out", "members/views.py",
     '    role = role if role in labels else ""\n', "", [REST]),
    ("no word when nobody matches", PAGE,
     "        {% elif filtering %}\n", "        {% elif False %}\n", [REST]),
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
