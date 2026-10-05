"""Round 201: break each rule once and check its test goes red (AGENTS.md
rule 7). Runs the tests first and stops if they are not green (083).
``--check`` only looks that every mutation still applies.

bash scripts/remote-check.sh run uv run python handoff/rounds/201-manual-notices/mutate.py
"""

import os
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
PY = sys.executable
ENV = {**os.environ, "PYTHONUTF8": "1"}

T = "tournaments/tests/test_time_changed.py::"
MOVED = T + "test_moving_mails_nobody_and_keeps_what_they_knew"
FIRST = T + "test_the_first_time_is_kept_and_moving_back_forgets_it"
PROMPT = T + "test_saving_in_the_admin_mails_nobody_and_says_who_does_not_know"
TOLD = T + "test_the_people_taking_part_hear_from_when_to_when"
REJECTED = T + "test_a_rejected_roster_does_not_hear"
S = "scrims/tests/test_time_changed.py::"
S_MOVED = S + "test_moving_mails_nobody_and_keeps_what_they_knew"
S_ADMIN = S + "test_saving_in_the_admin_mails_nobody_then_everyone_signed_up_hears"
S_DRAFT = S + "test_a_draft_cannot_notify_the_people_signed_up"
A = "core/tests/test_announcements.py::"
AGAIN = A + "test_a_manager_tells_everyone_and_may_again"
PREVIEW = A + "test_the_admin_previews_then_sends"
ARTICLE = A + "test_content_editors_announce_an_article"
PLANNED = A + "test_a_planned_article_is_announced_when_it_goes_live"
LIMITS = A + "test_articles_have_nobody_signed_up_and_a_note_has_a_limit"
ASK = "moderation/tests/test_ask_author.py::test_an_editor_writes_to_the_author"

MUTATIONS = [
    # --- saving notes the move instead of mailing
    ("every step kept, not the first", "tournaments/services.py",
     "    told = tournament.moved_from or old_starts_at",
     "    told = old_starts_at", [FIRST]),
    ("moving back still prompts", "tournaments/services.py",
     "    moved_from = None if told == new else told\n    Tournament",
     "    moved_from = told\n    Tournament", [FIRST]),
    ("the move not kept", "tournaments/services.py",
     "        reminder_sent_at=None, moved_from=moved_from\n    )\n    tournament.",
     "        reminder_sent_at=None\n    )\n    tournament.", [MOVED, PROMPT]),
    ("a scrim's move not kept", "scrims/services.py",
     "    told = scrim.moved_from or old_starts_at",
     "    told = new", [S_MOVED, S_ADMIN]),
    ("no prompt on the edit page", "backoffice/templates/backoffice/events/event_form.html",
     '{% if item.moved_from and item.status == "published" %}', "{% if False %}",
     [PROMPT, S_ADMIN]),
    # --- 「通知报名的人」
    ("the prompt stays after telling", "core/services.py",
     "        entry.model.objects.filter(pk=obj.pk).update(moved_from=None)\n", "",
     [TOLD, S_ADMIN]),
    ("the letter forgets the old time", "tournaments/notifications.py",
     "    moved = bool(\n        moved_from and tournament.starts_at and moved_from != tournament.starts_at\n    )",
     "    moved = False", [TOLD]),
    ("the admin's words dropped", "tournaments/notifications.py",
     '    paragraphs = [f"管理员的说明：{note}"] if note else []\n    if moved:\n        paragraphs.append(\n            "开赛前',
     '    paragraphs = []\n    if moved:\n        paragraphs.append(\n            "开赛前',
     [TOLD]),
    ("the worker forgets the old time", "core/services.py",
     "            moved_from=broadcast.moved_from,", "            moved_from=None,", [TOLD]),
    ("telling nobody is allowed", "core/services.py",
     '        if not entry.participants(obj):\n            return "还没有人报名，没有人可以通知。"\n',
     "", [REJECTED]),
    ("a draft's people told", "core/services.py",
     '        if not publishing and not entry.is_live(obj):\n            return "发布之后才能通知报名的人。"\n',
     "", [S_DRAFT]),
    ("the page always to everyone", "core/announce_admin.py",
     '    return services.PARTICIPANTS if asked == "participants" else services.EVERYONE',
     "    return services.EVERYONE", [S_ADMIN]),
    ("articles offered to the people signed up", "core/announce_admin.py",
     "    if to_participants and entry.participants is None:", "    if False:", [LIMITS]),
    ("any length of note", "core/services.py",
     "    if len(note) > NOTE_MAX:", "    if False:", [LIMITS]),
    ("no item for the people signed up", "backoffice/views/events.py",
     '        ("通知报名的人", "participants", url + "?to=participants"),\n', "",
     [PREVIEW]),
    # --- again, and saying so
    ("once only again", "core/services.py",
     "    entry = kinds()[kind]\n    if audience == PARTICIPANTS:\n        if entry.participants is None:",
     '    entry = kinds()[kind]\n    if history(kind, obj).filter(waits_for_publish=False).exists():\n        return "同一场只发一次。"\n    if audience == PARTICIPANTS:\n        if entry.participants is None:',
     [AGAIN, PREVIEW, ARTICLE]),
    ("a second plan for going live", "core/services.py",
     '        if waiting_broadcast(kind, obj) is not None:\n            return "已经安排在上线时通知全体成员，到时会发出，不用再安排。"\n',
     "", [PLANNED]),
    ("the article button gone once sent", "backoffice/views/articles.py",
     "    if not user_can_edit_author(user) or announced.get(page.pk, (0, False))[1]:",
     "    if not user_can_edit_author(user) or announced.get(page.pk, (0, False))[0]:",
     [ARTICLE]),
    ("the menu does not say how often", "backoffice/views/events.py",
     '        items.append(Item(f"{label}（发过 {times} 次）" if times else label, link))',
     "        items.append(Item(label, link))", [PREVIEW]),
    ("no notice on the second letter", "core/services.py",
     "    letter.notice = repeat_notice(kind, obj, before)",
     '    letter.notice = ""', [AGAIN, PREVIEW, ARTICLE]),
    ("every letter counted as the first", "core/services.py",
     "        before=history(kind, obj).count(),", "        before=0,", [AGAIN, ARTICLE]),
    ("the notice left out of the text", "core/letters.py",
     "    parts = [greeting(name), letter.notice, letter.lead]",
     "    parts = [greeting(name), letter.lead]", [AGAIN]),
    ("the notice left out of the HTML", "templates/email/letter.html",
     "{% if letter.notice %}", "{% if False %}", [AGAIN]),
    ("要求作者修改 says nothing the second time", "moderation/notifications.py",
     "        notice=notice,\n", "", [ASK]),
    ("要求作者修改 counts nothing", "moderation/services.py",
     "    transaction.on_commit(lambda: ask_author(item, message, before))",
     "    transaction.on_commit(lambda: ask_author(item, message))", [ASK]),
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
