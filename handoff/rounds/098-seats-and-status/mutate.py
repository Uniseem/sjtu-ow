"""Round 098 (branch claude/flat-muted-ui): break each new rule once and check
its test goes red (AGENTS.md rule 7). Runs the tests first and stops if they
are not green (083).

uv run python handoff/rounds/098-seats-and-status/mutate.py
"""

import os
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
PY = sys.executable
ENV = {**os.environ, "PYTHONUTF8": "1"}

T = "core/tests/test_flat_muted.py"
CSS = "assets/css/input.css"

MUTATIONS = [
    ("the pill comes back", CSS,
     "  .c-status--live {\n    --status: var(--color-accent);\n",
     "  .c-status--live {\n    --status: var(--color-accent);\n"
     "    background-color: var(--color-accent-soft);\n",
     [f"{T}::test_a_status_is_a_mark_and_a_word_not_a_pill"]),
    ("a status without its mark", CSS,
     '    background-color: var(--status);\n'
     '    -webkit-mask: url("../img/placeholders/peaks.svg") center / contain no-repeat;\n'
     '    mask: url("../img/placeholders/peaks.svg") center / contain no-repeat;\n',
     "",
     [f"{T}::test_a_status_is_a_mark_and_a_word_not_a_pill"]),
    ("taken seats counted from the end", "core/templatetags/ow.py",
     "    return [index < filled for index in range(cells)]",
     "    return [index >= cells - filled for index in range(cells)]",
     [f"{T}::test_places_are_counted_in_cells_not_a_bar"]),
    ("no ceiling on cells", "core/templatetags/ow.py",
     "    cells = min(total, MOST_SEATS)", "    cells = total",
     [f"{T}::test_places_are_counted_in_cells_not_a_bar"]),
    ("the bar comes back on the home page", "content/templates/content/home_page.html",
     '{% include "components/seats.html" with taken=row.count total=row.capacity %}',
     '<progress class="c-meter" value="{{ row.count }}" max="{{ row.capacity }}"></progress>',
     [f"{T}::test_places_are_counted_in_cells_not_a_bar"]),
    ("the rows stretch again", CSS,
     "    .c-upcoming--two > .c-feature {\n      aspect-ratio: auto;\n      min-height: 18rem;\n    }",
     "    .c-upcoming--two > .c-feature {\n      aspect-ratio: auto;\n      min-height: 18rem;\n    }\n\n"
     "    .c-upcoming--two > .c-rows > .c-row {\n      flex: 1;\n    }",
     [f"{T}::test_the_upcoming_scrims_keep_their_own_height"]),
    ("seats in the wrong colour", CSS,
     "  .c-seats > i.is-taken {\n    background-color: var(--color-accent);",
     "  .c-seats > i.is-taken {\n    background-color: var(--color-fg-3);",
     [f"{T}::test_places_are_counted_in_cells_not_a_bar"]),
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
