"""Round 130: break each new rule once and check its test goes red (AGENTS.md
rule 7). Runs the tests first and stops if they are not green (083).

bash scripts/remote-check.sh run uv run python handoff/rounds/130-submitter-editor/mutate.py
"""

import os
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
PY = sys.executable
ENV = {**os.environ, "PYTHONUTF8": "1"}

T = "content/tests/test_submitter_editor.py"
FIELDS = f"{T}::test_only_editors_and_authors_get_the_promote_fields"
KEPT = f"{T}::test_the_address_comes_from_the_title_and_survives_the_writer"
STEP = f"{T}::test_reserved_and_taken_addresses_step_aside"

MUTATIONS = [
    ("submitters keep the promote fields", "content/forms.py",
     "        if submits_for_review(user):\n            for name in EDITOR_ONLY_FIELDS:\n",
     "        if False:\n            for name in EDITOR_ONLY_FIELDS:\n", [FIELDS]),
    ("the schedule stays", "content/forms.py",
     '    "go_live_at",\n', "", [FIELDS]),
    ("Wagtail picks the address", "content/forms.py",
     '        if "slug" not in self.fields and not self.instance.slug:\n',
     "        if False:\n", [STEP]),
    ("the address is picked again on every save", "content/forms.py",
     '        if "slug" not in self.fields and not self.instance.slug:\n',
     '        if "slug" not in self.fields:\n', [KEPT]),
    ("reserved words are not stepped round", "content/forms.py",
     '            base = f"{base}-article"\n', "            pass\n", [STEP]),
    ("taken addresses are not stepped round", "content/forms.py",
     "        while not Page._slug_is_available(candidate, self.parent_page, self.instance):\n",
     "        while False:\n", [STEP]),
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
