"""Round 199: break each rule once and check its test goes red (AGENTS.md
rule 7). Runs the tests first and stops if they are not green (083).
``--check`` only looks that every mutation still applies.

bash scripts/remote-check.sh run uv run python handoff/rounds/199-placed-permissions/mutate.py
"""

import os
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
PY = sys.executable
ENV = {**os.environ, "PYTHONUTF8": "1"}

D = "backoffice/tests/test_door.py::"
BEFORE = D + "test_the_page_is_refused_before_its_view_runs"
NO_TAB = D + "test_a_tab_that_does_not_exist_is_caught_when_the_page_is_placed"
EVERY = D + "test_every_back_office_page_keeps_out_whoever_its_tab_is_not_for"
NO_LEAK = D + "test_no_page_tells_an_outsider_whether_an_id_exists"
DIALOG = D + "test_the_picture_dialog_is_for_people_who_may_use_pictures"
FINER = D + "test_new_and_delete_still_need_their_own_permission"

MUTATIONS = [
    ("the door does not ask the tab", "backoffice/nav.py",
     '            if not gate(request.user):\n                raise PermissionDenied("没有打开这一页的权限。")\n',
     "", [BEFORE, EVERY, NO_LEAK, DIALOG]),
    ("a stricter page as loose as its tab", "backoffice/nav.py",
     "    gate = allowed or (tab_for(section, tab).allowed if tab else access.can_enter)",
     "    gate = tab_for(section, tab).allowed if tab else access.can_enter",
     [BEFORE, EVERY, FINER]),
    ("a wrong tab placed quietly", "backoffice/nav.py",
     '    raise ValueError(f"「{BY_KEY[section].label}」里没有这个标签：{tab}")',
     "    return BY_KEY[section].tabs[0]", [NO_TAB]),
    ("collections for everyone with pictures", "backoffice/views/images.py",
     '@placed("content", "images", allowed=access.is_superuser)\ndef collection_list',
     '@placed("content", "images")\ndef collection_list', [EVERY, FINER]),
    ("a new category with change only", "backoffice/views/categories.py",
     '    if not pk:\n        _may(request, "add")\n', "", [FINER]),
    ("a category deleted with change only", "backoffice/views/categories.py",
     '    _may(request, "delete")\n', "", [FINER]),
    ("a new member group with change only", "backoffice/views/members.py",
     '    if not pk:\n        _group_may(request, "add")\n', "", [FINER]),
    ("a member group deleted with change only", "backoffice/views/members.py",
     '    _group_may(request, "delete")\n', "", [FINER]),
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
