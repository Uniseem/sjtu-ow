"""Round 127: break each new rule once and check its test goes red (AGENTS.md
rule 7). Runs the tests first and stops if they are not green (083).

uv run python handoff/rounds/127-article-announcements/mutate.py
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


def t(name):
    return f"{T}::{name}"


ANNOUNCE = t("test_content_editors_announce_an_article")
DRAFTS = t("test_drafts_and_other_roles_cannot_announce_articles")

MUTATIONS = [
    ("drafts count as published", "core/services.py",
     "            lambda obj: bool(obj.live),\n", "            lambda obj: True,\n",
     [DRAFTS]),
    ("any admin user may announce articles", "core/services.py",
     "            user_can_edit_author,\n            ArticlePage,\n",
     "            lambda user: True,\n            ArticlePage,\n",
     [DRAFTS]),
    ("the menu item shows on drafts", "content/wagtail_hooks.py",
     "    if not (issubclass(page_class, ArticlePage) and page.live):\n",
     "    if not issubclass(page_class, ArticlePage):\n",
     [DRAFTS]),
    ("the menu item shows to everyone", "content/wagtail_hooks.py",
     '    if not user_can_edit_author(user) or sent_broadcast("article", page):\n',
     '    if sent_broadcast("article", page):\n',
     [DRAFTS]),
    ("the menu item stays after sending", "content/wagtail_hooks.py",
     '    if not user_can_edit_author(user) or sent_broadcast("article", page):\n',
     "    if not user_can_edit_author(user):\n",
     [ANNOUNCE]),
    ("no item in the page list", "content/wagtail_hooks.py",
     '@hooks.register("register_page_listing_more_buttons")\n', "",
     [ANNOUNCE]),
    ("no item on the edit page", "content/wagtail_hooks.py",
     '@hooks.register("register_page_header_buttons")\n', "",
     [ANNOUNCE]),
    ("the subject ignores the category", "content/notifications.py",
     '    kind = category.name if category else "文章"\n', '    kind = "文章"\n',
     [ANNOUNCE]),
    ("the letter has no summary", "content/notifications.py",
     '        paragraphs=[page.summary] if getattr(page, "summary", "") else [],\n',
     "        paragraphs=[],\n",
     [ANNOUNCE]),
    ("no specimen", "core/email_samples.py",
     '            "new-article",\n', '            "new-article-gone",\n',
     [t("test_both_notices_are_on_the_specimen_page")]),
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
