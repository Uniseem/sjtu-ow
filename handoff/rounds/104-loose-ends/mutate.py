"""Round 104: break each new rule once and check its test goes red (AGENTS.md
rule 7). Runs the tests first and stops if they are not green (083).

uv run python handoff/rounds/104-loose-ends/mutate.py
"""

import os
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
PY = sys.executable
ENV = {**os.environ, "PYTHONUTF8": "1"}

DEL = "accounts/tests/test_account_deletion.py"
AV = "accounts/tests/test_avatar.py"
OPS = "core/tests/test_ops_commands.py"
SVC = "accounts/services.py"
CMD = "core/management/commands/restore.py"

MUTATIONS = [
    ("deletion keeps the motto", SVC, '        user.motto = ""\n', "",
     [f"{DEL}::test_deleting_clears_the_public_profile"]),
    ("deletion keeps the main position", SVC, '        user.main_role = ""\n', "",
     [f"{DEL}::test_deleting_clears_the_public_profile"]),
    ("deletion keeps the other positions", SVC, '        user.flex_roles = ""\n', "",
     [f"{DEL}::test_deleting_clears_the_public_profile"]),
    ("the review queue keeps the motto", SVC,
     "            target_type__in=[TargetType.NICKNAME, TargetType.MOTTO],\n",
     "            target_type__in=[TargetType.NICKNAME],\n",
     [f"{DEL}::test_deleting_drops_the_review_queues_copies_of_the_nickname"]),
    ("listings are not refreshed for authors", SVC,
     '        refresh_listings("article")\n', "        pass\n",
     [f"{AV}::test_an_authors_new_face_reaches_the_homepage_and_listings"]),
    ("listings are refreshed for everyone", SVC,
     "    if ArticlePage.objects.live().public().filter(author=user).exists():\n",
     "    if True:\n",
     [f"{AV}::test_an_authors_new_face_reaches_the_homepage_and_listings"]),
    ("tests write to the project media", "conftest.py",
     '    settings.MEDIA_ROOT = tmp_path_factory.mktemp("media")\n',
     "    pass\n",
     ["core/tests/test_isolation.py::test_uploads_in_tests_never_reach_the_project_media_folder"]),
    ("the database goes in before the uploads", CMD,
     "            connection.close()\n"
     "            database.parent.mkdir(parents=True, exist_ok=True)\n"
     "            for path in wal_siblings(database):\n"
     "                if path.exists():\n"
     "                    path.unlink()\n"
     "            shutil.copy2(snapshot, database)\n\n"
     "            empty_folder(prerendered)\n",
     "            empty_folder(prerendered)\n",
     [f"{OPS}::test_a_failed_upload_copy_leaves_the_database_alone"]),
]
# The last one moves the database copy above the media block (see apply).


def run(tests):
    return subprocess.run(
        [PY, "-m", "pytest", "-q", "-x", "-p", "no:cacheprovider", *tests],
        cwd=ROOT, env=ENV, capture_output=True, text=True,
    ).returncode


def apply(text, label, old, new):
    if label == "the database goes in before the uploads":
        # Move the database copy above the media block.
        anchor = "            staged_media = staging / \"media\"\n"
        assert text.count(old) == 1 and text.count(anchor) == 1, label
        block = old.replace("            empty_folder(prerendered)\n", "")
        text = text.replace(old, new)
        return text.replace(anchor, block + anchor)
    assert text.count(old) == 1, (label, text.count(old))
    return text.replace(old, new)


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
            text = apply(raw.replace("\r\n", "\n"), label, old, new)
            path.write_bytes((text.replace("\n", "\r\n") if crlf else text).encode("utf-8"))
            for test in tests:
                red = run([test]) != 0
                print(("caught " if red else "MISSED ") + label + " -> " + test.split("::")[1])
                if not red:
                    failed.append((label, test))
        finally:
            shutil.copy2(backup, path)
            backup.unlink()
            folder = rel.rsplit("/", 1)[0] if "/" in rel else "."
            for cache in ROOT.glob(folder + "/__pycache__/*.pyc"):
                cache.unlink()
    assert run(every) == 0, "not green after restoring"
    print("restored and green;", "missed:", failed or "none")
    return 1 if failed else 0


sys.exit(main())
