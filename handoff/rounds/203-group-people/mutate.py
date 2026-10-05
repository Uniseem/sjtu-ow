"""Round 203: break each rule once and check its test goes red (AGENTS.md
rule 7). Runs the tests first and stops if they are not green (083).
``--check`` only looks that every mutation still applies.

bash scripts/remote-check.sh run uv run python handoff/rounds/203-group-people/mutate.py
"""

import os
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
PY = sys.executable
ENV = {**os.environ, "PYTHONUTF8": "1"}

M = "members/tests/test_members.py::"
FIND = M + "test_an_admin_finds_people_and_adds_them_with_one_click"
ORDER = M + "test_people_are_reordered_given_posts_and_taken_out"
PLAIN = M + "test_without_the_script_everything_still_works"
JOINED = M + "test_someone_who_has_not_joined_cannot_be_added"
UNNAMED = M + "test_an_unnamed_group_can_be_opened_again"
A = "core/tests/test_autosave.py::"
NEW = A + "test_a_new_member_group_exists_at_once_with_its_people_block"
CATEGORY = A + "test_a_new_category_exists_from_the_first_change_and_hides_unnamed"
AVATAR = A + "test_the_avatar_goes_as_soon_as_it_is_chosen"

MUTATIONS = [
    ("people already in are found again", "members/services.py",
     "        people = people.exclude(member_groups__group=group)\n", "", [FIND]),
    ("people who have not joined are found", "members/services.py",
     "    people = joined_users().filter(\n",
     "    people = joined_users().model.objects.filter(\n", [FIND]),
    ("someone who has not joined is added", "members/services.py",
     "    if not is_joined(user):", "    if False:", [JOINED]),
    ("the same person added twice", "members/services.py",
     "        if group.memberships.filter(user=user).exists():", "        if False:", [FIND]),
    ("a new person put first", "members/services.py",
     "sort_order=0 if last is None else last + 1", "sort_order=0 if last is None else last - 1",
     [FIND]),
    ("up moves down", "members/services.py",
     "    other = index + step", "    other = index - step", [ORDER]),
    ("any post taken", "members/services.py",
     "    if len(title) > 20 or any(len(post) > 10 for post in split_titles(title)):",
     "    if False:", [ORDER]),
    ("a new group without its people block", "backoffice/views/members.py",
     '        replace["[data-memberships]"] = _people_html(request, group)\n', "", [NEW]),
    ("the script gets a page instead of the block", "backoffice/views/members.py",
     '    if "application/json" in request.headers.get("Accept", ""):', "    if False:",
     [FIND, ORDER, JOINED]),
    ("no search without the script", "backoffice/views/members.py",
     '        "found": member_services.search_people(group, query),', '        "found": [],',
     [PLAIN]),
    ("an unnamed group's link is empty", "backoffice/templates/backoffice/members/groups.html",
     '{{ group.name|default:"（未命名分组）" }}', "{{ group.name }}", [UNNAMED]),
    ("an unnamed category's link is empty", "backoffice/templates/backoffice/content/categories.html",
     '{{ item.name|default:"（未命名分类）" }}', "{{ item.name }}", [CATEGORY]),
    ("the avatar box marked as a must", "accounts/forms.py",
     "        required=False,\n    )\n", "    )\n", [AVATAR]),
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
