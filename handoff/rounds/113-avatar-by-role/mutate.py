"""Round 113: break each new rule once and check its test goes red (AGENTS.md
rule 7). Runs the tests first and stops if they are not green (083).

uv run python handoff/rounds/113-avatar-by-role/mutate.py
"""

import os
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
PY = sys.executable
ENV = {**os.environ, "PYTHONUTF8": "1"}

T = "accounts/tests/test_default_avatar.py"
AVATARS = "core/avatars.py"

MUTATIONS = [
    ("the position is ignored", AVATARS,
     "    same = [image for image in images if role and image.face_role == role]\n",
     "    same = []\n",
     [f"{T}::test_a_tank_gets_a_tank_face_and_a_support_a_support_face"]),
    ("no main position means no face", AVATARS,
     "    choices = same or images\n",
     "    choices = same or images[:1]\n",
     [f"{T}::test_without_a_main_position_any_face"]),
    ("an empty position folder breaks the page", AVATARS,
     "    choices = same or images\n",
     "    choices = same if role else images\n",
     [f"{T}::test_an_empty_position_folder_falls_back_to_the_whole_pool"]),
    ("only faces right in the position folder count", AVATARS,
     '        image.face_role = folders.get(image.collection.path[:top], "")\n',
     '        image.face_role = folders.get(image.collection.path, "")\n',
     [f"{T}::test_folders_under_a_position_folder_count_for_it"]),
    ("folders are matched by the wrong name", AVATARS,
     "ROLE_BY_FOLDER = {label: code for code, label in ROLE_CHOICES}\n",
     "ROLE_BY_FOLDER = {code: code for code, label in ROLE_CHOICES}\n",
     [f"{T}::test_a_tank_gets_a_tank_face_and_a_support_a_support_face"]),
    ("the other positions are ignored", AVATARS,
     '    return others[0] if others else ""\n',
     '    return ""\n',
     [f"{T}::test_without_a_main_position_the_first_other_one_counts"]),
    ("the last other position is used", AVATARS,
     '    return others[0] if others else ""\n',
     '    return others[-1] if others else ""\n',
     [f"{T}::test_without_a_main_position_the_first_other_one_counts"]),
    ("each face looks its folder up", AVATARS,
     '        .select_related("collection")\n', "",
     [f"{T}::test_loading_the_pool_costs_the_same_however_many_faces"]),
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
