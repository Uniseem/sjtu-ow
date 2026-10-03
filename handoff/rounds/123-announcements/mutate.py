"""Round 123: break each new rule once and check its test goes red (AGENTS.md
rule 7). Runs the tests first and stops if they are not green (083).

uv run python handoff/rounds/123-announcements/mutate.py
"""

import os
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
PY = sys.executable
ENV = {**os.environ, "PYTHONUTF8": "1"}

T = "core/tests/test_announcements.py"
SERVICES = "core/services.py"


def t(name):
    return f"{T}::{name}"


MUTATIONS = [
    ("people who turned it off still get it", SERVICES,
     "        accepts_announcements=True,\n", "",
     [t("test_only_active_verified_members_who_left_it_on"), t("test_people_who_turned_it_off_meanwhile_are_skipped")]),
    ("unverified addresses get it", SERVICES,
     "        emailaddress__verified=True,\n", "",
     [t("test_only_active_verified_members_who_left_it_on")]),
    ("SJTU-only events tell everyone", SERVICES,
     "        people = people.filter(is_sjtu=True)\n", "        pass\n",
     [t("test_sjtu_only_events_tell_sjtu_members_only")]),
    ("deactivated accounts can use old links", SERVICES,
     "    return User.objects.filter(pk=pk, is_active=True).first()\n",
     "    return User.objects.filter(pk=pk).first()\n",
     [t("test_a_deactivated_account_link_is_dead")]),
    ("anyone may announce", SERVICES,
     "    if not entry.can_send(actor):\n", "    if False:\n",
     [t("test_no_smtp_no_drafts_no_strangers")]),
    ("drafts can be announced", SERVICES,
     '    if not publishing and getattr(obj, "status", "") != "published":\n', "    if False:\n",
     [t("test_no_smtp_no_drafts_no_strangers")]),
    ("announcing without SMTP", SERVICES,
     "        build_smtp_backend(SiteSettings.load())\n", "        pass\n",
     [t("test_no_smtp_no_drafts_no_strangers")]),
    ("the same event twice", SERVICES,
     "    problem = announcement_problem(kind, obj)\n", '    problem = ""\n',
     [t("test_a_manager_tells_everyone_once")]),
    ("nothing is queued", SERVICES,
     "    transaction.on_commit(lambda: send_broadcast.enqueue(broadcast.pk))\n", "",
     [t("test_a_manager_tells_everyone_once")]),
    ("letters carry no unsubscribe header", "core/letters.py",
     '            "List-Unsubscribe": f"<{letter.unsubscribe}>",\n', "",
     [t("test_a_manager_tells_everyone_once")]),
    ("letters carry no unsubscribe link", "core/letters.py",
     '    unsubscribe = f"\\n退订活动通知：{letter.unsubscribe}" if letter.unsubscribe else ""\n',
     '    unsubscribe = ""\n',
     [t("test_a_manager_tells_everyone_once"), t("test_both_notices_are_on_the_specimen_page")]),
    ("the unsubscribe link does nothing", "core/views.py",
     "        set_announcements(person, False)\n", "        pass\n",
     [t("test_the_unsubscribe_link_asks_then_turns_it_off")]),
    ("mail clients hit the CSRF check", "core/views.py",
     "@csrf_exempt\ndef announcements_unsubscribe(request, token):\n",
     "def announcements_unsubscribe(request, token):\n",
     [t("test_a_mail_client_can_unsubscribe_in_one_click")]),
    ("publishing ignores the box", "tournaments/wagtail_hooks.py",
     '            if action == "publish" and request.POST.get("announce"):\n',
     "            if False:\n",
     [t("test_publishing_can_tell_everyone")]),
    ("publishing always announces", "tournaments/wagtail_hooks.py",
     '            if action == "publish" and request.POST.get("announce"):\n',
     '            if action == "publish":\n',
     [t("test_publishing_can_tell_everyone")]),
    ("the account switch always turns it on", "accounts/views.py",
     '    accepts = request.POST.get("accepts_announcements") == "1"\n',
     "    accepts = True\n",
     [t("test_members_switch_it_in_account_security")]),
    ("the worker sends nothing", SERVICES,
     "        sent += send(\n", "        sent += 0 and send(\n",
     [t("test_the_worker_task_delivers"), t("test_people_who_turned_it_off_meanwhile_are_skipped")]),
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
