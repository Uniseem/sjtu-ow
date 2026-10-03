"""Round 136: break each new rule once and check its test goes red (AGENTS.md
rule 7). Runs the tests first and stops if they are not green (083).

bash scripts/remote-check.sh run uv run python handoff/rounds/136-team-contact/mutate.py
"""

import os
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
PY = sys.executable
ENV = {**os.environ, "PYTHONUTF8": "1"}

T = "teams/tests/test_member_contact.py"


def t(name):
    return f"{T}::{name}"


SETS = t("test_the_captain_sets_it_on_the_manage_page")
SEE = t("test_only_members_see_it")
SLOT = "teams/templates/teams/slots/join.html"
INCLUDE = '    {% include "teams/_member_contact.html" %}\n'

MUTATIONS = [
    ("members do not see it", SLOT,
     '    </form>\n' + INCLUDE, "    </form>\n", [SEE]),
    ("everyone sees it", SLOT,
     "  {% endif %}\n</div>", '  {% endif %}\n  {% include "teams/_member_contact.html" %}\n</div>',
     [SEE]),
    ("the service ignores it", "teams/services.py",
     "        team.member_contact = member_contact.strip()\n", "        pass\n",
     [t("test_the_service_saves_it_trimmed")]),
    ("not trimmed", "teams/services.py",
     "        team.member_contact = member_contact.strip()\n",
     "        team.member_contact = member_contact\n", [t("test_the_service_saves_it_trimmed")]),
    # The view passing member_contact on is equivalent: the bound ModelForm has
    # already written it onto ``team`` (as for every other field there).
    ("asked for on the create form", "teams/forms.py",
     '            self.fields.pop("member_contact", None)\n', "", [SETS]),
    ("the welcome letter leaves it out", "teams/notifications.py",
     "            facts=contact,\n", "", [t("test_the_welcome_letter_says_how_to_reach_them")]),
    ("no nudge for the captain", "teams/templates/teams/_member_contact.html",
     "{% elif is_captain %}", "{% elif False %}", [t("test_the_captain_is_nudged_to_fill_it")]),
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
