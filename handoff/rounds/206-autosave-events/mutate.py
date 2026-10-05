"""Round 206: break each rule once and check its test goes red (AGENTS.md
rule 7). Runs the tests first and stops if they are not green (083).
``--check`` only looks that every mutation still applies.

bash scripts/remote-check.sh run uv run python handoff/rounds/206-autosave-events/mutate.py
"""

import os
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
PY = sys.executable
ENV = {**os.environ, "PYTHONUTF8": "1"}

E = "core/tests/test_autosave_events.py::"
NEW_CUP = E + "test_a_new_tournament_exists_from_its_first_change"
NEW_SCRIM = E + "test_a_new_scrim_exists_with_its_start_still_empty"
COPY = E + "test_a_copy_keeps_what_it_copied_when_a_field_is_wrong"
RULE = E + "test_a_rule_across_fields_holds_back_one_field"
KEEP = E + "test_a_published_one_keeps_its_required_fields"
ONCE = E + "test_saving_again_and_again_arranges_each_task_once"
MOMENT = E + "test_a_page_refresh_counts_only_at_the_same_moment"
EARLIER = E + "test_an_earlier_waiting_reminder_is_enough_a_later_one_is_not"
WAIT = E + "test_a_reminder_due_while_editing_waits_ten_minutes"
CUP_WAIT = E + "test_a_tournament_reminder_waits_too"

MUTATIONS = [
    ("a new tournament waits for its required fields", "backoffice/views/events.py",
     "    if obj.pk is None:\n        obj, outcome.saved = autosave.new_from_valid_fields(form, fresh())",
     "    if obj.pk is None and valid:\n        obj, outcome.saved = autosave.new_from_valid_fields(form, fresh())",
     [NEW_CUP, NEW_SCRIM]),
    ("a new draft listed last", "backoffice/views/events.py",
     '        F("registration_opens_at").desc(nulls_first=True),',
     '        "-registration_opens_at",', [NEW_CUP]),
    ("a tournament published with gaps", "tournaments/services.py",
     "    gaps = missing(tournament)\n    if gaps:\n        raise TournamentError",
     "    gaps = []\n    if gaps:\n        raise TournamentError", [NEW_CUP]),
    ("the publish page does not say what is missing", "tournaments/admin_views.py",
     '"missing": services.missing(tournament) if action == "publish" else [],',
     '"missing": [],', [NEW_CUP]),
    ("a scrim published without a start", "scrims/services.py",
     '    if scrim.starts_at is None:\n        gaps.append("开始时间")',
     "    if False:\n        pass", [NEW_SCRIM]),
    ("a half-filled draft cancelled", "scrims/services.py",
     "    if scrim.status == ScrimStatus.DRAFT and missing(scrim):\n        # Cancelled",
     "    if False:\n        # Cancelled", [NEW_SCRIM]),
    ("a copy starts from blank, not from what it copied", "backoffice/views/events.py",
     '            lambda: tournament_services.copy_for_new(source),',
     "            Tournament,", [COPY]),
    ("the window rule stops the whole form", "backoffice/forms.py",
     '            self.add_error("registration_closes_at", "报名截止时间要晚于报名开始时间。")',
     '            raise ValidationError("报名截止时间要晚于报名开始时间。")', [RULE]),
    ("the roster rule left to the database", "backoffice/forms.py",
     '        elif low and high and low > high:\n            self.add_error("roster_max", "人数上限不能小于下限。")',
     "        elif False:\n            pass", [COPY]),
    ("a published title emptied", "backoffice/forms.py",
     "        cap = services.team_max_members()\n",
     '        self.fields["title"].required = False\n        cap = services.team_max_members()\n',
     [KEEP]),
    ("every save arranges its tasks again", "core/tasks.py",
     "        if args_kwargs != wanted:\n            continue\n",
     "        continue\n", [ONCE]),
    ("an earlier refresh counts for a later moment", "core/tasks.py",
     "        if earlier_counts and (at_once or due <= run_after):",
     "        if at_once or due <= run_after:", [MOMENT]),
    ("a later reminder counts for an earlier one", "core/tasks.py",
     "        if earlier_counts and (at_once or due <= run_after):",
     "        if earlier_counts:", [EARLIER]),
    ("a reminder in the window goes at once", "core/tasks.py",
     "    due = max(run_at, now + REMINDER_GRACE)\n",
     "    due = max(run_at, now)\n", [WAIT, CUP_WAIT]),
    ("a reminder too close to the start never goes", "core/tasks.py",
     "    return due if due < starts_at else max(run_at, now)",
     "    return due", [WAIT]),
    ("scrim reminders not once", "scrims/services.py",
     "        enqueue_once(send_scrim_reminder, scrim_id, run_after=due, earlier_counts=True)",
     "        send_scrim_reminder.using(run_after=due).enqueue(scrim_id)", [ONCE]),
    ("auto-finish not once", "scrims/services.py",
     "        enqueue_once(finish_past_scrim, scrim_id, run_after=run_at, earlier_counts=True)",
     "        finish_past_scrim.using(run_after=run_at).enqueue(scrim_id)", [ONCE]),
    ("tournament reminders not once", "tournaments/services.py",
     "        enqueue_once(\n            send_tournament_reminder, tournament_id, run_after=due, earlier_counts=True\n        )",
     "        send_tournament_reminder.using(run_after=due).enqueue(tournament_id)", [CUP_WAIT]),
]


def run(tests):
    return subprocess.run(
        [PY, "-m", "pytest", "-q", "-x", "-p", "no:cacheprovider", *tests],
        cwd=ROOT,
        env=ENV,
        capture_output=True,
        text=True,
    ).returncode


def _text(rel):
    return (ROOT / rel).read_bytes().decode("utf-8").replace("\r\n", "\n")


def check():
    bad = [
        (label, _text(rel).count(old))
        for label, rel, old, _new, _tests in MUTATIONS
        if _text(rel).count(old) != 1
    ]
    print("mutations:", len(MUTATIONS), "not applying:", bad or "none")
    return not bad


def main():
    if not check():
        sys.exit(1)
    if "--check" in sys.argv:
        return
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
            text = raw.replace("\r\n", "\n").replace(old, new)
            path.write_bytes(
                (text.replace("\n", "\r\n") if crlf else text).encode("utf-8")
            )
            for test in tests:
                red = run([test]) != 0
                print(("caught " if red else "MISSED ") + label + " -> " + test.split("::")[1])
                if not red:
                    failed.append((label, test))
        finally:
            shutil.copy2(backup, path)
            backup.unlink()
            folder = rel.rsplit("/", 1)[0]
            for cache in ROOT.glob(folder + "/**/__pycache__/*.pyc"):
                cache.unlink()
    assert run(every) == 0, "not green after restoring"
    print("restored and green;", "missed:", failed or "none")


if __name__ == "__main__":
    main()
