"""Round 137: break each new rule once and check its test goes red (AGENTS.md
rule 7). Runs the tests first and stops if they are not green (083).

bash scripts/remote-check.sh run uv run python handoff/rounds/137-participant-contact/mutate.py
"""

import os
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
PY = sys.executable
ENV = {**os.environ, "PYTHONUTF8": "1"}

T = "tournaments/tests/test_participant_contact.py"


def t(name):
    return f"{T}::{name}"


PAGE = t("test_the_tournament_page_shows_it_to_participants_only")
DETAIL = t("test_the_registration_page_shows_it_while_live")
LETTERS = t("test_the_letters_to_participants_carry_it")
DETAIL_HTML = "tournaments/templates/tournaments/registration_detail.html"

MUTATIONS = [
    ("left rosters still take part", "tournaments/registration.py",
     "        tournament.roster_members.filter(user=user, is_active=True).exists()\n",
     "        tournament.roster_members.filter(user=user).exists()\n",
     [t("test_who_takes_part")]),
    ("the pool does not take part", "tournaments/registration.py",
     "        or tournament.individual_signups.filter(user=user).exists()\n", "",
     [t("test_the_pool_sees_it_too")]),
    ("everyone signed in sees it", "tournaments/slots.py",
     "            and registration_service.takes_part(tournament, user)\n", "", [PAGE]),
    ("the slot leaves it out", "tournaments/templates/tournaments/slots/actions.html",
     "  {% if participant_contact %}<p", "  {% if False %}<p", [PAGE]),
    ("dead registrations show it", DETAIL_HTML,
     "        {% if registration.status in active_statuses and registration.tournament.participant_contact %}\n",
     "        {% if registration.tournament.participant_contact %}\n", [DETAIL]),
    ("the registration page leaves it out", DETAIL_HTML,
     "        {% if registration.status in active_statuses and registration.tournament.participant_contact %}\n",
     "        {% if False %}\n", [DETAIL]),
    ("letters leave it out", "tournaments/notifications.py",
     '    return [("选手联系方式", contact)] if contact else []\n', "    return []\n", [LETTERS]),
    ("a rejection carries it too", "tournaments/notifications_registration.py",
     "    if registration.status == RegistrationStatus.APPROVED:\n        facts.extend(_contact(registration))\n",
     "    facts.extend(_contact(registration))\n", [LETTERS]),
    ("not in the admin form", "tournaments/wagtail_hooks.py",
     '        FieldPanel("participant_contact"),\n', "", [t("test_the_admin_form_has_it")]),
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
