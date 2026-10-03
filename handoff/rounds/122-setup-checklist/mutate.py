"""Round 122: break each new rule once and check its test goes red (AGENTS.md
rule 7). Runs the tests first and stops if they are not green (083).

uv run python handoff/rounds/122-setup-checklist/mutate.py
"""

import os
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
PY = sys.executable
ENV = {**os.environ, "PYTHONUTF8": "1"}

T = "core/tests/test_setup_checklist.py"
SETUP = "core/admin_setup.py"


def t(name):
    return f"{T}::{name}"


MUTATIONS = [
    ("mail counts as done without SMTP", SETUP,
     "    done = bool(site.smtp_host and site.from_address)\n", "    done = True\n",
     [t("test_mail_is_a_must_until_smtp_is_set")]),
    ("blanks in the agreement pass", SETUP,
     "                bool(text.strip()) and not blanks,\n", "                bool(text.strip()),\n",
     [t("test_the_agreements_need_their_blanks_filled")]),
    ("the AI check blames the switch for a missing key", SETUP,
     "    if not services.is_configured():\n        detail = (\n",
     "    if False:\n        detail = (\n",
     [t("test_ai_says_whether_the_key_or_the_switch_is_missing")]),
    ("backup without the key counts as done", SETUP,
     "    done = bool(site.backup_s3_enabled and key)\n", "    done = bool(site.backup_s3_enabled)\n",
     [t("test_suggestions_turn_done")]),
    ("nobody in 内容编辑 counts as done", SETUP,
     "    done = bool(group and group.user_set.filter(is_active=True).exists())\n", "    done = bool(group)\n",
     [t("test_suggestions_turn_done")]),
    ("the test banner never shows up", SETUP,
     '    on = bool(getattr(settings, "TEST_ENVIRONMENT", False))\n', "    on = False\n",
     [t("test_suggestions_turn_done")]),
    ("no checklist on the dashboard", "core/wagtail_hooks.py",
     "        panels.insert(1, SetupPanel())\n", "        pass\n",
     [t("test_mail_is_a_must_until_smtp_is_set")]),
    ("everyone sees the checklist", "core/wagtail_hooks.py",
     "    if request.user.is_superuser:\n        panels.insert(1, SetupPanel())\n",
     "    if True:\n        panels.insert(1, SetupPanel())\n",
     [t("test_only_superusers_see_the_checklist")]),
    ("init_site leaves the agreements empty", "core/management/commands/init_site.py",
     '        call_command("load_legal_pages", stdout=self.stdout, verbosity=0)\n', "",
     [t("test_init_site_fills_the_agreements_and_says_what_is_next")]),
    ("init_site says nothing about what is next", "core/management/commands/init_site.py",
     "        self.stdout.write(NEXT_STEPS)\n", "",
     [t("test_init_site_fills_the_agreements_and_says_what_is_next")]),
    ("trying the AI is not counted", "moderation/services.py",
     "    note_usage(\n        calls=1,\n        items=1,\n",
     "    (lambda **kwargs: None)(\n        calls=1,\n        items=1,\n",
     [t("test_trying_the_ai_reports_success_and_counts_the_call")]),
    ("a bad key gets no hint", "moderation/services.py",
     '        if "401" in reason or "403" in reason:\n', "        if False:\n",
     [t("test_a_bad_key_says_so")]),
    ("the page hides why AI is off", "moderation/templates/moderation/index.html",
     "  {% if disabled_reason %}\n", "  {% if False %}\n",
     [t("test_without_a_key_the_page_says_why_and_offers_no_try")]),
    ("the try button shows without a key", "moderation/templates/moderation/index.html",
     "  {% if configured %}\n", "  {% if True %}\n",
     [t("test_without_a_key_the_page_says_why_and_offers_no_try")]),
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
