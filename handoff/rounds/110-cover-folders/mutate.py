"""Round 110: break each new rule once and check its test goes red (AGENTS.md
rule 7). Runs the tests first and stops if they are not green (083).

uv run python handoff/rounds/110-cover-folders/mutate.py
"""

import os
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
PY = sys.executable
ENV = {**os.environ, "PYTHONUTF8": "1"}

T = "core/tests/test_cover_pool.py"
COVERS = "core/covers.py"

MUTATIONS = [
    ("folders under the pool are left out", COVERS,
     "        .objects.filter(collection__path__startswith=root.path)\n",
     "        .objects.filter(collection=root)\n",
     [f"{T}::test_the_folders_under_the_pool_are_in_it"]),
    ("a collection beside the pool counts", COVERS,
     "        .objects.filter(collection__path__startswith=root.path)\n",
     "        .objects.filter(collection__path__startswith=root.path[:-4])\n",
     [f"{T}::test_the_folders_under_the_pool_are_in_it"]),
    ("moves into a folder are missed", COVERS,
     "        Collection.objects.filter(pk=collection_id, path__startswith=root.path).exists()\n",
     "        Collection.objects.filter(pk=collection_id, pk__in=[root.pk]).exists()\n",
     [f"{T}::test_moving_a_picture_into_or_out_of_a_folder_regenerates"]),
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
