"""Round 205: break each rule once and check its test goes red (AGENTS.md
rule 7). Runs the tests first and stops if they are not green (083).
``--check`` only looks that every mutation still applies.

bash scripts/remote-check.sh run uv run python handoff/rounds/205-autosave-drafts/mutate.py
"""

import os
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
PY = sys.executable
ENV = {**os.environ, "PYTHONUTF8": "1"}

D = "content/tests/test_drafts.py::"
DRAFT = D + "test_an_article_saves_itself_as_a_draft"
STRETCH = D + "test_one_stretch_of_editing_is_one_revision"
OTHER = D + "test_someone_else_starts_their_own_draft"
NEW = D + "test_a_new_article_exists_from_its_first_change"
SLUG = D + "test_the_address_follows_the_title_until_published"
PARTIAL = D + "test_a_bad_field_keeps_its_value_and_the_rest_is_saved"
PLAIN = D + "test_a_plain_page_waits_for_publish"
PINS = D + "test_the_pins_and_the_intro_wait_for_publish"
EDITOR = D + "test_the_editor_saves_after_a_pause_not_per_keystroke"
WRITES = "backoffice/tests/test_backoffice.py::test_a_member_writes_saves_and_publishes"

MUTATIONS = [
    ("an autosave publishes", "backoffice/views/articles.py",
     "    elif saved:\n        save_draft(page, draft, user)\n",
     "    elif saved:\n        save_draft(page, draft, user)\n"
     "        from wagtail.actions.publish_page_revision import PublishPageRevisionAction\n"
     "        PublishPageRevisionAction(page.get_latest_revision()).execute()\n",
     [DRAFT]),
    ("every save a new revision", "content/drafts.py",
     "        user=user, clean=False, overwrite_revision=overwritable(page, user)",
     "        user=user, clean=False, overwrite_revision=None", [STRETCH]),
    ("someone else's draft overwritten", "content/drafts.py",
     "    if latest is None or user is None or latest.user_id != user.pk:",
     "    if latest is None or user is None:", [OTHER]),
    ("the live revision overwritten", "content/drafts.py",
     "    if latest.pk == page.live_revision_id or latest.approved_go_live_at is not None:",
     "    if latest.approved_go_live_at is not None:", [STRETCH]),
    ("an old draft overwritten", "content/drafts.py",
     "    if latest.created_at < timezone.now() - OVERWRITE_WITHIN:\n        return None\n",
     "", [STRETCH]),
    ("each autosave logged", "content/drafts.py",
     "    log_edit(page, user)\n",
     "    from wagtail.log_actions import log\n\n    log(page, \"wagtail.edit\", user=user)\n",
     [STRETCH]),
    ("a new article waits for its title", "backoffice/views/articles.py",
     "    if page is None:\n        page = start_article(parent, draft, user)\n        outcome.location",
     "    if page is None and valid:\n        page = start_article(parent, draft, user)\n        outcome.location",
     [NEW]),
    ("the address fixed on the first save", "backoffice/forms.py",
     "        return not original or original == self._free_slug(self._original_title)",
     "        return not original", [SLUG]),
    ("a typed address follows the title", "backoffice/forms.py",
     '            return not self.cleaned_data.get("slug", self._original_slug)',
     "            return True", [SLUG]),
    ("a published address follows the title", "backoffice/forms.py",
     "        if page.first_published_at is not None:\n            return False\n",
     "", [SLUG]),
    ("the page not told the new address", "backoffice/views/articles.py",
     '        outcome.values["slug"] = draft.slug\n', "        pass\n", [SLUG]),
    ("a bad field saves nothing", "backoffice/views/articles.py",
     "    elif saved:\n", "    elif saved and valid:\n", [PARTIAL]),
    ("a plain page published on save", "backoffice/views/pages.py",
     "            save_draft(page, form.instance, request.user)  # the fine fields applied",
     "            PublishPageRevisionAction(save_draft(page, form.instance, request.user)).execute()",
     [PLAIN]),
    ("the pins go live on save", "backoffice/views/pages.py",
     "            if valid and saved:\n                save_draft(home, draft, request.user)",
     "            if valid and saved:\n                PublishPageRevisionAction(save_draft(home, draft, request.user)).execute()",
     [PINS]),
    ("the intro goes live on save", "backoffice/views/pages.py",
     "            if valid and saved:\n                save_draft(index, draft, request.user)",
     "            if valid and saved:\n                PublishPageRevisionAction(save_draft(index, draft, request.user)).execute()",
     [PINS]),
    ("「发布」 does not publish", "backoffice/views/pages.py",
     '    if "publish" in request.POST:\n        PublishPageRevisionAction',
     '    if False:\n        PublishPageRevisionAction', [PINS]),
    ("the editor saves per keystroke", "static/js/markdown-editor.js",
     '      textarea.dispatchEvent(new Event("input", { bubbles: true }));\n    });',
     '      textarea.dispatchEvent(new Event("input", { bubbles: true }));\n'
     '      textarea.dispatchEvent(new Event("change", { bubbles: true }));\n    });',
     [EDITOR]),
    ("no form save without the script", "backoffice/views/articles.py",
     '    if "publish" in request.POST:\n        if page.permissions_for_user(user).can_publish():',
     '    if True:\n        if page.permissions_for_user(user).can_publish():', [WRITES]),
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
