"""Round 121: break each new rule once and check its test goes red (AGENTS.md
rule 7). Runs the tests first and stops if they are not green (083).

uv run python handoff/rounds/121-ask-author/mutate.py
"""

import os
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
PY = sys.executable
ENV = {**os.environ, "PYTHONUTF8": "1"}

T = "moderation/tests/test_ask_author.py"
SERVICES = "moderation/services.py"


def t(name):
    return f"{T}::{name}"


MUTATIONS = [
    ("no mail goes out", SERVICES,
     "    transaction.on_commit(lambda: ask_author(item, message))\n", "",
     [t("test_an_editor_writes_to_the_author")]),
    ("the item stays pending", SERVICES,
     "    item.status = ModerationItem.Status.HANDLED\n", "",
     [t("test_an_editor_writes_to_the_author")]),
    ("the message is not kept", SERVICES,
     '        data={"result": "要求作者修改（已发信）", "note": message},\n',
     '        data={"result": "要求作者修改（已发信）"},\n',
     [t("test_an_editor_writes_to_the_author")]),
    ("the history hides the mail", "moderation/admin_views.py",
     "            .filter(action__in=[HANDLE_LOG_ACTION, services.REVISE_LOG_ACTION])\n",
     "            .filter(action__in=[HANDLE_LOG_ACTION])\n",
     [t("test_an_editor_writes_to_the_author")]),
    ("the letter leaves out the message", "moderation/notifications.py",
     '        paragraphs=[f"管理员的说明：{message}", "改完保存就行，不用回复这封邮件。"],\n',
     '        paragraphs=["改完保存就行，不用回复这封邮件。"],\n',
     [t("test_an_editor_writes_to_the_author")]),
    ("teams have nowhere to fix it", "moderation/notifications.py",
     '    if kind in ("team_name", "team_description"):\n',
     '    if kind in ("team_name",):\n',
     [t("test_an_editor_writes_to_the_author"), t("test_each_kind_of_content_has_somewhere_to_fix_it")]),
    ("deactivated authors get mail", SERVICES,
     "    if not author.is_active:\n", "    if False:\n",
     [t("test_no_author_or_a_deactivated_one_gets_no_form_and_no_mail")]),
    ("the page offers the form anyway", "moderation/templates/moderation/detail.html",
     "  {% if author_problem %}\n", "  {% if False %}\n",
     [t("test_no_author_or_a_deactivated_one_gets_no_form_and_no_mail")]),
    ("the service skips the author check", SERVICES,
     "    problem = author_problem(item)\n", '    problem = ""\n',
     [t("test_no_author_or_a_deactivated_one_gets_no_form_and_no_mail")]),
    ("an empty message goes out", SERVICES,
     "    if not message:\n", "    if False:\n",
     [t("test_an_empty_or_long_message_is_refused")]),
    ("a long message goes out", SERVICES,
     "    if len(message) > REVISE_MAX_CHARS:\n", "    if False:\n",
     [t("test_an_empty_or_long_message_is_refused")]),
    ("anyone may write", "moderation/admin_views.py",
     '@reviewer_required\n@require_POST\ndef moderation_ask_author(request, pk):\n',
     '@require_POST\ndef moderation_ask_author(request, pk):\n',
     [t("test_only_reviewers_can_write")]),
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
