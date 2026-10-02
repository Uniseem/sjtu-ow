"""Round 093: break each new rule once and check its test goes red (AGENTS.md
rule 7). Runs the tests first and stops if they are not green (083).

uv run python handoff/rounds/093-registration-mode/mutate.py
"""

import os
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
PY = sys.executable
ENV = {**os.environ, "PYTHONUTF8": "1"}

RM = "tournaments/tests/test_registration_mode.py"
IS = "tournaments/tests/test_individual_signup.py"

MUTATIONS = [
    ("teams by default", "tournaments/models.py",
     "        default=RegistrationMode.INDIVIDUAL,\n",
     "        default=RegistrationMode.TEAM,\n",
     [f"{RM}::test_a_new_tournament_takes_individuals"]),
    ("the migration makes everyone individual", "tournaments/migrations/0008_registration_mode.py",
     '    Tournament.objects.filter(allow_individual_signup=False).update(\n        registration_mode="team"\n    )\n',
     "",
     [f"{RM}::test_the_old_switch_becomes_the_mode"]),
    ("teams enter an individual tournament", "tournaments/registration.py",
     "    if not tournament.takes_teams:\n", "    if False:\n",
     [f"{RM}::test_an_individual_tournament_refuses_a_team_entry"]),
    ("individuals enter a team tournament", "tournaments/registration.py",
     "    if not tournament.takes_individuals:\n", "    if False:\n",
     [f"{IS}::test_a_team_tournament_takes_no_individuals"]),
    ("a pool entry does not lock the mode", "tournaments/services.py",
     "    return has_registrations(tournament) or tournament.individual_signups.exists()",
     "    return has_registrations(tournament)",
     [f"{RM}::test_the_mode_locks_once_anyone_has_signed_up"]),
    ("the mode never locks", "tournaments/wagtail_hooks.py",
     '        if "registration_mode" in self.changed_data and services.has_entries(',
     '        if False and services.has_entries(',
     [f"{RM}::test_the_mode_locks_once_anyone_has_signed_up"]),
    ("captains lose the individual entry", "tournaments/templates/tournaments/slots/actions.html",
     "  {% elif tournament.takes_individuals %}\n", "  {% elif False %}\n",
     [f"{IS}::test_a_captain_signs_up_alone_when_people_sign_up_alone"]),
    ("captains get no team entry", "tournaments/slots.py",
     "        captain_teams = captain_teams_for(user)\n", "        captain_teams = []\n",
     [f"{IS}::test_a_captain_enters_the_team_when_teams_enter"]),
    ("a member on the roster is not told", "tournaments/templates/tournaments/slots/actions.html",
     "  {% elif on_roster %}\n", "  {% elif False %}\n",
     [f"{RM}::test_a_member_entered_by_the_captain_sees_the_team"]),
    ("a withdrawn roster still shows", "tournaments/slots.py",
     "                    members__is_active=True,\n", "",
     [f"{RM}::test_a_member_entered_by_the_captain_sees_the_team"]),
    ("members are not told by mail", "tournaments/registration.py",
     "    mails.team_members_entered(registration, entered)\n", "",
     [f"{RM}::test_members_hear_when_entered_and_a_sync_tells_only_the_new"]),
    ("a sync tells everyone again", "tournaments/registration.py",
     "        row for row in rows if not row.is_captain and row.user_id not in already_on\n",
     "        row for row in rows if not row.is_captain\n",
     [f"{RM}::test_members_hear_when_entered_and_a_sync_tells_only_the_new"]),
    ("the captain is mailed too", "tournaments/registration.py",
     "        row for row in rows if not row.is_captain and row.user_id not in already_on\n",
     "        row for row in rows if row.user_id not in already_on\n",
     [f"{RM}::test_members_hear_when_entered_and_a_sync_tells_only_the_new"]),
    ("the page hides the mode", "tournaments/templates/tournaments/detail.html",
     '        <span class="c-tag" data-mode-tag>{{ tournament.get_registration_mode_display }}</span>\n',
     "",
     [f"{RM}::test_the_page_says_how_people_sign_up"]),
    ("a team tournament shows a pool", "tournaments/templates/tournaments/detail.html",
     "        {% if tournament.takes_individuals %}\n          <section aria-labelledby=\"t-pool\">\n",
     "        {% if True %}\n          <section aria-labelledby=\"t-pool\">\n",
     [f"{RM}::test_the_page_says_how_people_sign_up"]),
    ("cards hide the mode", "templates/components/tournament_card.html",
     '<p class="c-media__facts">{{ tournament.get_registration_mode_display }} · ',
     '<p class="c-media__facts">',
     [f"{RM}::test_the_cards_lead_with_the_mode"]),
    ("the form hides that nobody confirms", "tournaments/templates/tournaments/register.html",
     "<strong class=\"text-fg\">不需要队员确认</strong>", "",
     [f"{RM}::test_the_entry_form_says_nobody_confirms"]),
    ("the board on team tournaments", "tournaments/wagtail_hooks.py",
     "        if instance.takes_individuals:\n", "        if True:\n",
     [f"{RM}::test_the_team_board_is_offered_only_where_people_sign_up_alone"]),
    ("the scrim banner plain again", "scrims/templates/scrims/detail.html",
     '    <img src="{{ scrim|cover_placeholder }}" width="2400" height="900" class="c-stage__img" alt="">\n',
     "",
     [f"{RM}::test_a_scrim_banner_is_its_placeholder_picture"]),
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
            for cache in ROOT.glob(rel.rsplit("/", 1)[0] + "/__pycache__/*.pyc"):
                cache.unlink()
    assert run(every) == 0, "not green after restoring"
    print("restored and green;", "missed:", failed or "none")
    return 1 if failed else 0


sys.exit(main())
