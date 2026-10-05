"""Round 202: break each rule once and check its test goes red (AGENTS.md
rule 7). Runs the tests first and stops if they are not green (083).
``--check`` only looks that every mutation still applies.

bash scripts/remote-check.sh run uv run python handoff/rounds/202-autosave/mutate.py

The script itself (static/js/autosave.js) is checked in the browser by
scripts/journey.py (the new-member and the officers' runs).
"""

import os
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
PY = sys.executable
ENV = {**os.environ, "PYTHONUTF8": "1"}

A = "core/tests/test_autosave.py::"
RULE = A + "test_a_rule_across_fields_holds_back_what_it_names_or_everything"
PROFILE = A + "test_the_profile_keeps_what_is_fine_and_says_what_is_not"
AVATAR = A + "test_the_avatar_goes_as_soon_as_it_is_chosen"
SETTINGS = A + "test_site_settings_keep_the_key_and_the_good_fields"
USERS = A + "test_user_edits_save_themselves_and_stopping_is_a_button"
CATEGORY = A + "test_a_new_category_exists_from_the_first_change_and_hides_unnamed"
GROUP = A + "test_a_new_member_group_and_its_rows"
TEAM = A + "test_a_clashing_team_name_does_not_hold_back_the_rest"
PICTURES = A + "test_pictures_and_collections_save_themselves"
TYPE = A + "test_typography_saves_each_row_and_merges_the_regeneration"
PATROL = A + "test_the_patrol_reads_the_latest_text_not_each_half"
LOG = A + "test_one_log_entry_per_stretch_of_editing"
OWN = "backoffice/tests/test_backoffice.py::test_nobody_switches_their_own_account_off"

MUTATIONS = [
    # --- the rule (core/autosave.py)
    ("only whole forms saved", "core/autosave.py",
     "    names = valid_changes(form)\n    instance = form.instance\n",
     "    names = []\n    instance = form.instance\n", [PROFILE, SETTINGS, TEAM]),
    ("fields checked together saved anyway", "core/autosave.py",
     "        bad |= set(together)", "        pass", [RULE]),
    ("a rule naming nothing holds back nothing", "core/autosave.py",
     "        if not together:\n            return []\n", "", [RULE]),
    ("errors not said", "core/autosave.py",
     '            "errors": outcome.errors,', '            "errors": {},',
     [PROFILE, SETTINGS, USERS]),
    ("every post taken for an autosave", "core/autosave.py",
     '    return request.method == "POST" and request.headers.get(HEADER) == "1"',
     '    return request.method == "POST"', [PROFILE]),
    ("a log entry per autosave", "core/autosave.py",
     "    if recent is not None:", "    if False:", [LOG, SETTINGS]),
    ("one entry for everyone's edits", "core/autosave.py",
     "        .filter(action=action, user=user, timestamp__gte=timezone.now() - LOG_MERGE)",
     "        .filter(action=action, timestamp__gte=timezone.now() - LOG_MERGE)", [LOG]),
    # --- the patrol reads the latest
    ("every half-typed text kept for the patrol", "moderation/services.py",
     '    stale = waiting.order_by("-created_at").first()', "    stale = None", [PATROL]),
    ("what was read gets replaced", "moderation/services.py",
     "    waiting = same_place.filter(checked_at__isnull=True).exclude(text_hash=digest)",
     "    waiting = same_place.exclude(text_hash=digest)", [PATROL]),
    # --- unnamed ones stay out of sight
    ("unnamed categories shown", "content/models.py",
     '        return self.exclude(name="").exclude(slug="")', "        return self.all()",
     [CATEGORY]),
    ("unnamed categories offered to articles", "backoffice/forms.py",
     '        self.fields["category"].queryset = ArticleCategory.objects.named()\n', "",
     [CATEGORY]),
    ("unnamed groups on /members/", "members/services.py",
     '        .exclude(name="")\n', "", [GROUP]),
    ("a taken address only a page error", "backoffice/forms.py",
     "        if slug and taken.exists():", "        if False:", [CATEGORY]),
    ("a taken team name a server error", "backoffice/forms.py",
     "        if name and name_taken(name, exclude_pk=self.instance.pk):", "        if False:",
     [TEAM]),
    # --- new ones and their rows
    ("a new group gets no address", "backoffice/views/members.py",
     '        location = reverse("backoffice:member_group_edit", args=[group.pk])\n', "",
     [GROUP]),
    ("new rows' ids not handed back", "backoffice/views/members.py",
     "                if formset.new_objects or formset.deleted_objects:", "                if False:",
     [GROUP]),
    # --- the pages
    ("roles not saved by autosave", "backoffice/views/members.py",
     "        if \"roles\" in autosave.valid_changes(form):\n            form.save_roles()\n",
     "        if \"roles\" in autosave.valid_changes(form):\n            pass\n", [USERS]),
    ("stopped without a reason", "backoffice/views/members.py",
     "    form = DeactivateForm(request.POST)\n    if not form.is_valid():",
     "    form = DeactivateForm(request.POST)\n    if False:", [USERS]),
    ("anyone stops their own account", "backoffice/views/members.py",
     "    if person.pk == request.user.pk:\n        messages.error(request, \"不能在这里停用自己的账号。\")",
     "    if False:\n        messages.error(request, \"不能在这里停用自己的账号。\")", [OWN]),
    ("a blank collection name taken", "backoffice/views/images.py",
     "    if autosave.wants(request):\n        if collection.is_root() or not name:",
     "    if autosave.wants(request):\n        if collection.is_root():", [PICTURES]),
    ("a picture's title not written", "backoffice/views/images.py",
     "            image.save(update_fields=names)\n", "            pass\n", [PICTURES]),
    ("a full regeneration per autosave", "core/fonts/css.py",
     "        prerender.request_all_soon()", "        prerender.request_all()", [TYPE]),
    ("the avatar waits for a button", "templates/me/profile.html",
     'class="c-form" data-autosubmit-file>', 'class="c-form">', [AVATAR]),
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
