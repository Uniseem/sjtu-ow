"""Round 185: break each new rule once and check its test goes red (AGENTS.md
rule 7). Runs the tests first and stops if they are not green (083).

bash scripts/remote-check.sh run uv run python handoff/rounds/185-admin-link/mutate.py
"""

import os
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
PY = sys.executable
ENV = {**os.environ, "PYTHONUTF8": "1"}

T = "core/tests/test_admin_link.py"


def t(name):
    return f"{T}::{name}"


OWNER = t("test_the_site_owner_is_shown_the_way_in")
EDITOR = t("test_so_is_a_content_editor")
MEMBER = t("test_members_and_visitors_are_not")
TT = "core/templatetags/ow.py"

MUTATIONS = [
    ("no link in the menu", "templates/components/account_area.html", "{% if user|runs_admin %}<a href=", "{% if False %}<a href=", [OWNER, EDITOR]),
    ("no link in the footer", "templates/slots/footer_account.html", "{% if request.user|runs_admin %}<a href=", "{% if False %}<a href=", [OWNER, EDITOR]),
    ("submitters get it too", TT, ' and not is_submitter_only(user)\n', "\n", [MEMBER]),
    ("everyone signed in gets it", TT, '    return user.has_perm("wagtailadmin.access_admin") and not is_submitter_only(user)\n', "    return True\n", [MEMBER]),
    ("nobody gets it", TT, '    return user.has_perm("wagtailadmin.access_admin") and not is_submitter_only(user)\n', "    return False\n", [OWNER, EDITOR]),
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
