"""Round 103: break each new rule once and check its test goes red (AGENTS.md
rule 7). Runs the tests first and stops if they are not green (083).

uv run python handoff/rounds/103-restore-media/mutate.py
"""

import os
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
PY = sys.executable
ENV = {**os.environ, "PYTHONUTF8": "1"}

T = "core/tests/test_ops_commands.py"
CMD = "core/management/commands/restore.py"
MOUNT = f"{T}::test_restore_works_when_media_is_a_mounted_volume"
EXACT = f"{T}::test_restore_brings_the_uploads_back_and_drops_the_rest"

MUTATIONS = [
    ("media is removed and copied again (the old way)", CMD,
     "                empty_folder(media)\n"
     "                shutil.copytree(staged_media, media, dirs_exist_ok=True)\n",
     "                if media.exists():\n"
     "                    shutil.rmtree(media)\n"
     "                shutil.copytree(staged_media, media)\n",
     [MOUNT]),
    ("copying refuses an existing folder", CMD,
     "shutil.copytree(staged_media, media, dirs_exist_ok=True)",
     "shutil.copytree(staged_media, media)",
     [MOUNT, EXACT]),
    ("media is not emptied first", CMD,
     "                empty_folder(media)\n", "",
     [EXACT]),
    ("emptying removes the folder itself", CMD,
     "    for child in folder.iterdir():\n"
     "        if child.is_dir() and not child.is_symlink():\n"
     "            shutil.rmtree(child)\n"
     "        else:\n"
     "            child.unlink()\n",
     "    shutil.rmtree(folder)\n",
     [MOUNT]),
    ("the static pages are left", CMD,
     "            empty_folder(prerendered)\n", "",
     [MOUNT, f"{T}::test_restore_replaces_the_database_and_clears_prerendered"]),
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
            for cache in ROOT.glob(rel.rsplit("/", 1)[0] + "/__pycache__/*.pyc"):
                cache.unlink()
    assert run(every) == 0, "not green after restoring"
    print("restored and green;", "missed:", failed or "none")
    return 1 if failed else 0


sys.exit(main())
