"""Round 204: break each rule once and check its test goes red (AGENTS.md
rule 7). Runs the tests first and stops if they are not green (083).
``--check`` only looks that every mutation still applies.

bash scripts/remote-check.sh run uv run python handoff/rounds/204-send-after-asking/mutate.py
"""

import os
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
PY = sys.executable
ENV = {**os.environ, "PYTHONUTF8": "1"}

H = "core/tests/test_held_letters.py::"
AT_ONCE = H + "test_outside_a_request_the_letter_goes_at_once"
WAITS = H + "test_inside_an_action_the_letter_waits_written_down_whole"
ONE = H + "test_the_same_letter_to_more_people_is_one_letter"
CUP = H + "test_a_cancelled_tournament_is_one_letter_to_all_its_people"
RACE = H + "test_two_clicks_at_once_send_once"
TICKED = H + "test_only_the_ticked_letters_go_and_only_once"
VOID = H + "test_a_letter_left_seven_days_is_void"
TIMED = H + "test_timed_reminders_go_by_themselves_even_during_a_request"
HELD = H + "test_every_letter_an_action_brings_is_held"
GONE = H + "test_nobody_left_to_ask_means_the_letters_go"
DELETED = H + "test_deleting_the_account_drops_its_letters"
APPLY = H + "test_a_member_applies_and_is_asked_before_the_captain_is_mailed"
SKIP = H + "test_not_sending_sends_nothing"
OTHERS = H + "test_nobody_else_opens_or_sends_them"
POINTED = H + "test_letters_left_waiting_are_pointed_at"
SCRIM = H + "test_an_admin_cancels_a_scrim_and_is_asked_in_the_back_office"
CLEANUP = H + "test_the_daily_cleanup_drops_old_letters"

MUTATIONS = [
    ("letters never wait", "core/outbox.py",
     "    if batch is None:\n        return send_to(", "    if True:\n        return send_to(",
     [WAITS, APPLY]),
    ("outside a request nothing goes", "core/outbox.py",
     "        return send_to(letter, pairs, fail_silently=fail_silently)\n",
     "        return 0\n", [AT_ONCE]),
    ("the same letter twice is two", "core/outbox.py",
     "        if row.letter == frozen:", "        if False:", [ONE, CUP]),
    ("every letter goes, ticked or not", "core/outbox.py",
     "        state = HeldLetter.State.SENT if row.pk in keep else HeldLetter.State.SKIPPED",
     "        state = HeldLetter.State.SENT", [TICKED]),
    ("a letter sent twice", "core/outbox.py",
     "        claimed = HeldLetter.objects.filter(\n            pk=row.pk, state=HeldLetter.State.WAITING\n        )",
     "        claimed = HeldLetter.objects.filter(\n            pk=row.pk\n        )", [RACE]),
    ("letters never go void", "core/outbox.py",
     "        created_at__gte=timezone.now() - WAIT,\n", "", [VOID]),
    ("someone else's letters are theirs too", "core/outbox.py",
     "        actor=actor,\n        state=HeldLetter.State.WAITING,", "        state=HeldLetter.State.WAITING,",
     [OTHERS]),
    ("asked even with nobody there", "core/outbox.py",
     "    if not (user and user.is_authenticated and user.pk == batch.actor.pk):",
     "    if False:", [GONE]),
    ("the action does not go on to 「发信」", "core/outbox.py",
     "    if not redirected:\n", "    if True:\n", [APPLY, SCRIM]),
    ("「都不发」 sends the ticked ones", "core/held_views.py",
     '        if not request.POST.get("skip"):', "        if True:", [SKIP]),
    ("the middleware does not ask", "sjtu_ow/settings/base.py",
     '    "core.middleware.HeldLettersMiddleware",\n', "", [APPLY, SCRIM]),
    ("an application mails the captain at once", "teams/notifications.py",
     "    hold(application_submitted_letter(application), [captain])",
     "    send(application_submitted_letter(application), [captain])", [HELD, APPLY]),
    ("a cancelled scrim mails at once", "scrims/notifications.py",
     "    return hold(scrim_cancelled_letter(scrim)", "    return send(scrim_cancelled_letter(scrim)",
     [HELD, SCRIM]),
    ("a timed reminder waits", "teams/notifications.py",
     "    send(applications_waiting_letter(team, applications), [captain])",
     "    hold(applications_waiting_letter(team, applications), [captain])", [TIMED]),
    ("no reminder in the personal center", "templates/me/base.html",
     '        {% include "me/_letters.html" %}\n', "", [POINTED]),
    ("no to-do in the back office", "core/admin_todo.py",
     "        _letter_rows(user)\n        + ", "        ", [SCRIM]),
    ("letters outlive the account", "accounts/services.py",
     "        HeldLetter.objects.filter(actor=user).delete()  # design 10.5\n", "", [DELETED]),
    ("old letters kept forever", "core/management/commands/cleanup_old_data.py",
     '        yield (f"做完事写的信（{TASK_DAYS} 天前）", self.held_letters(now))',
     "        pass", [CLEANUP]),
    ("the back office asks in the site's look", "core/outbox.py",
     "    in_back_office = request.path.startswith(BACK_OFFICE)",
     "    in_back_office = False", [SCRIM]),
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
