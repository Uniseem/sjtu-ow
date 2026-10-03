"""Round 129: break each new rule once and check its test goes red (AGENTS.md
rule 7). Runs the tests first and stops if they are not green (083).

bash scripts/remote-check.sh run uv run python handoff/rounds/129-tournament-reminder/mutate.py
"""

import os
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
PY = sys.executable
ENV = {**os.environ, "PYTHONUTF8": "1"}

T = "tournaments/tests/test_reminder.py"


def t(name):
    return f"{T}::{name}"


ARRANGED = t("test_publishing_arranges_it_a_day_before")
NO_START = t("test_no_start_time_no_reminder")
EACH = t("test_each_approved_player_gets_their_own")
APPROVED_ONLY = t("test_only_approved_rosters_hear")
SKIPPED = t("test_players_who_left_or_were_deactivated_are_skipped")
HELD = t("test_a_later_start_or_a_cancellation_holds_it")
APPROVAL = t("test_the_approval_says_when_to_show_up")
SPECIMEN = t("test_the_reminder_is_on_the_specimen_page")

MUTATIONS = [
    ("saving does not arrange it", "tournaments/services.py",
     "    schedule_phase_refresh(tournament)\n    schedule_reminder(tournament)\n",
     "    schedule_phase_refresh(tournament)\n", [ARRANGED]),
    ("the setting is ignored", "tournaments/services.py",
     '    return int(getattr(SiteSettings.load(), "tournament_reminder_hours", 24) or 24)\n',
     "    return 24\n", [ARRANGED]),
    ("arranged without a start time", "tournaments/services.py",
     "        or tournament.starts_at is None\n", "", [NO_START]),
    ("the task runs without a start time", "tournaments/tasks.py",
     '    if tournament.starts_at is None:\n        return "no_start"\n', "", [NO_START]),
    ("sent twice", "tournaments/tasks.py",
     '    if tournament.reminder_sent_at is not None:\n        return "already_sent"\n', "",
     [EACH]),
    ("cancelled still reminds", "tournaments/tasks.py",
     '    if tournament.status != TournamentStatus.PUBLISHED:\n        return "not_published"\n',
     "", [HELD]),
    ("early, not rescheduled", "tournaments/tasks.py",
     "    if now < due:\n", "    if False:\n", [HELD]),
    ("marked sent with nobody to tell", "tournaments/tasks.py",
     "    if sent:\n        Tournament.objects.filter(",
     "    if True:\n        Tournament.objects.filter(", [APPROVED_ONLY]),
    ("pending rosters hear too", "tournaments/notifications.py",
     "        registration__status=RegistrationStatus.APPROVED,\n", "", [APPROVED_ONLY]),
    ("players who left hear too", "tournaments/notifications.py",
     "        tournament=tournament,\n        is_active=True,\n",
     "        tournament=tournament,\n", [SKIPPED]),
    ("deactivated accounts hear too", "tournaments/notifications.py",
     "        if not (row.user.is_active and row.user.email):\n",
     "        if not row.user.email:\n", [SKIPPED]),
    ("the letter leaves out the game ID", "tournaments/notifications.py",
     '            ("你的游戏 ID", row.battletag or "未填"),\n        ],',
     "        ],", [EACH]),
    ("the approval leaves out the time", "tournaments/notifications_registration.py",
     '        facts.append(("比赛时间", moment(starts_at)))\n', "        pass\n", [APPROVAL]),
    ("a rejection gives a time too", "tournaments/notifications_registration.py",
     "    if registration.status == RegistrationStatus.APPROVED and starts_at:\n",
     "    if starts_at:\n", [APPROVAL]),
    ("/healthz lets a database error through", "core/health.py",
     "    heartbeat_ok, heartbeat_detail = _reported(check_worker_heartbeat)\n",
     "    heartbeat_ok, heartbeat_detail = check_worker_heartbeat()\n",
     ["core/tests/test_pages.py::"
      "test_a_read_only_database_with_an_expired_heartbeat_still_answers"]),
    ("no specimen", "core/email_samples.py",
     '            "tournament-reminder",\n', '            "tournament-reminder-gone",\n',
     [SPECIMEN]),
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
