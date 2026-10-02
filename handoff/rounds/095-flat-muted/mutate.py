"""Round 095 (branch claude/flat-muted-ui): break each new rule once and check
its test goes red (AGENTS.md rule 7). Runs the tests first and stops if they
are not green (083).

uv run python handoff/rounds/095-flat-muted/mutate.py
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
    ("the loud orange comes back", CSS,
     "  --color-accent: #cf9152;", "  --color-accent: #f99e1a;",
     [f"{T}::test_every_colour_token_is_restrained"]),
    ("the loud red comes back", CSS,
     "  --color-primary: #9b3a33;", "  --color-primary: #a4161a;",
     [f"{T}::test_every_colour_token_is_restrained"]),
    ("a loud base picture", "core/placeholders.py",
     '"top": "#3a2228", "bottom": "#b0706a"', '"top": "#2a0a12", "bottom": "#c0393f"',
     [f"{T}::test_the_base_pictures_are_muted_too"]),
    ("the horizon in the band's colour", CSS,
     "    background-color: var(--page-bg);\n", "    background-color: var(--color-bg);\n",
     [f"{T}::test_picture_heads_sink_into_the_page_under_a_horizon"]),
    ("no page ground kept", CSS,
     "  --page-bg: var(--color-bg);\n", "",
     [f"{T}::test_picture_heads_sink_into_the_page_under_a_horizon"]),
    ("a rule under the ridge", CSS,
     "  .c-pagehead--picture,\n  .c-stage:not(.c-stage--plain) {\n    border-bottom: 0;\n  }\n",
     "",
     [f"{T}::test_picture_heads_sink_into_the_page_under_a_horizon"]),
    ("the far ridge is solid", "core/placeholders.py",
     'enumerate(("url(#mist)", "#000"))', 'enumerate(("#000", "#000"))',
     [f"{T}::test_the_horizon_fades_its_far_ridge_like_the_art"]),
    ("titles without peaks", CSS,
     '    mask: url("../img/placeholders/peaks.svg") center / contain no-repeat;\n',
     "",
     [f"{T}::test_section_titles_carry_the_peaks"]),
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
