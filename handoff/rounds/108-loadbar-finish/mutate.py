"""Round 108: break each new rule once and check its test goes red (AGENTS.md
rule 7). Runs the tests first and stops if they are not green (083).

uv run python handoff/rounds/108-loadbar-finish/mutate.py
"""

import os
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
PY = sys.executable
ENV = {**os.environ, "PYTHONUTF8": "1"}

T = "core/tests/test_transitions.py"
CSS = "assets/css/input.css"
LOADING = "static/js/loading.js"
ARRIVAL = "static/js/arrival.js"
FINISH = f"{T}::test_on_the_next_page_the_bar_runs_to_the_end_then_fades"
READS = f"{T}::test_the_next_page_reads_where_the_bar_was_before_its_first_paint"
SAW = f"{T}::test_only_a_bar_the_visitor_saw_is_finished"
NOTES = f"{T}::test_leaving_notes_where_the_bar_got_to"

MUTATIONS = [
    ("the bar does not run to the end", CSS,
     "      transform: scaleX(1);\n    }\n  }\n\n  @keyframes ow-loadbar-fade {",
     "      transform: scaleX(0.9);\n    }\n  }\n\n  @keyframes ow-loadbar-fade {",
     [FINISH]),
    ("the bar runs on linearly", CSS,
     "ow-loadbar-finish 300ms cubic-bezier(0.2, 0, 0, 1) both",
     "ow-loadbar-finish 300ms linear both", [FINISH]),
    ("the bar fades before it is full", CSS,
     "ow-loadbar-fade 250ms ease 300ms forwards", "ow-loadbar-fade 250ms ease forwards",
     [FINISH]),
    ("the bar starts from nothing", CSS,
     "transform: scaleX(var(--loadbar-from, 0.6));", "transform: scaleX(0);",
     [FINISH]),
    ("arrival.js not in the head", "templates/base.html",
     "    <script src=\"{% static 'js/arrival.js' %}\"></script>\n", "",
     [READS]),
    ("the note is kept for later pages", ARRIVAL,
     "      window.sessionStorage.removeItem(KEY);\n", "",
     [READS]),
    ("old notes are trusted", ARRIVAL,
     " || Date.now() - note.at > FRESH", "", [READS]),
    ("a prepared page reads while prepared", ARRIVAL,
     "if (document.prerendering) {", "if (false) {", [READS]),
    ("the note is written at once", LOADING,
     "    }, SHOWN_AFTER);\n", "    }, 0);\n", [SAW]),
    ("the two scripts use different notes", ARRIVAL,
     'var KEY = "ow-loading";', 'var KEY = "ow-bar";', [SAW]),
    ("the delays drift apart", LOADING,
     "var SHOWN_AFTER = 150;", "var SHOWN_AFTER = 300;", [SAW]),
    ("a new load keeps the old note", LOADING,
     "    window.clearTimeout(shown);\n    note(null);\n    // Only a bar",
     "    window.clearTimeout(shown);\n    // Only a bar", [SAW]),
    ("leaving does not note the place", LOADING,
     "    current.from = progress();\n", "", [NOTES]),
    ("leaving notes a bar that never showed", LOADING,
     '    if (!root.classList.contains("is-loading") || !current) {',
     '    if (!root.classList.contains("is-loading")) {', [NOTES]),
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
    assert run(every) == 0, "not green after restoring"
    print("restored and green;", "missed:", failed or "none")
    return 1 if failed else 0


sys.exit(main())
