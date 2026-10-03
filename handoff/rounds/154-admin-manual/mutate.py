"""Round 154: break each new rule once and check its test goes red (AGENTS.md
rule 7). Runs the tests first and stops if they are not green (083).

bash scripts/remote-check.sh run uv run python handoff/rounds/154-admin-manual/mutate.py
"""

import os
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
PY = sys.executable
ENV = {**os.environ, "PYTHONUTF8": "1"}

T = "core/tests/test_admin_manual.py"
ROLES = f"{T}::test_each_role_gets_its_parts"
PAGE = f"{T}::test_the_page_and_its_menu"
M = "core/admin_manual.py"

MUTATIONS = [
    ("everyone gets the tournament part", M,
     "    if tournament_services.can_manage(user):\n", "    if True:\n", [ROLES]),
    ("superusers miss the content part", M,
     "    if user.is_superuser or GROUP_CONTENT in groups:\n", "    if GROUP_CONTENT in groups:\n",
     [ROLES]),
    ("no owner part", M, "    if user.is_superuser:\n        parts.append(OWNER)\n", "", [ROLES]),
    ("authors get nothing", M,
     "        parts.append(AUTHORS)\n", "        pass\n", [ROLES]),
    # The menu item's is_shown is equivalent for pure submitters: their
    # admin menu is cut down to 首页 and 图片 anyway (design 14.3).
    ("submitters open the page", M,
     "    if not parts:\n        raise PermissionDenied", "    if False:\n        raise PermissionDenied",
     [PAGE]),
    ("steps lose their links", "core/templates/core/admin/manual.html",
     '{% if url %} <a href="{{ url }}">{{ label }} →</a>{% endif %}', "", [PAGE]),
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
