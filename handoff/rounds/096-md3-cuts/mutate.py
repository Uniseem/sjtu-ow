"""Round 096 (branch claude/flat-muted-ui): break each new rule once and check
its test goes red (AGENTS.md rule 7). Runs the tests first and stops if they
are not green (083).

uv run python handoff/rounds/096-md3-cuts/mutate.py
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
    ("the warm paper comes back", CSS,
     "  --color-bg: #f5f6f8;", "  --color-bg: #f1eee8;",
     [f"{T}::test_the_light_neutrals_have_no_warm_cast"]),
    ("warm text comes back", CSS,
     "  --color-fg-2: #4a505b;", "  --color-fg-2: #4d4a45;",
     [f"{T}::test_the_light_neutrals_have_no_warm_cast"]),
    ("a card is outlined again", CSS,
     "  .c-person {\n", "  .c-person {\n    border: 1px solid var(--color-line);\n",
     [f"{T}::test_nothing_is_outlined_only_toned_apart"]),
    ("table rows are ruled again", CSS,
     "    border-top: 2px solid var(--color-bg);\n    vertical-align: middle;",
     "    border-top: 1px solid var(--color-line);\n    vertical-align: middle;",
     [f"{T}::test_nothing_is_outlined_only_toned_apart",
      f"{T}::test_a_list_is_a_group_of_tiles"]),
    ("the list is one box", CSS,
     "    flex-direction: column;\n    gap: 3px;\n  }",
     "    flex-direction: column;\n    gap: 0;\n  }",
     [f"{T}::test_a_list_is_a_group_of_tiles"]),
    ("the tiles' inner corners round off", CSS,
     "  .c-rows > .c-row {\n    border-radius: var(--radius-xs);",
     "  .c-rows > .c-row {\n    border-radius: var(--radius-lg);",
     [f"{T}::test_a_list_is_a_group_of_tiles"]),
    ("the transition ridge is solid", "core/placeholders.py",
     'HORIZON_STEP = "0.5"', 'HORIZON_STEP = "1"',
     [f"{T}::test_the_horizon_steps_down_in_two_flat_ridges"]),
    ("the horizon stands still", CSS,
     "    animation: c-horizon 120s linear infinite;\n", "",
     [f"{T}::test_the_horizon_drifts_without_a_seam"]),
    ("the near ridge drifts no faster", CSS,
     "      mask-position:\n        -1600px 100%,\n        -3200px 100%;",
     "      mask-position:\n        -1600px 100%,\n        -1600px 100%;",
     [f"{T}::test_the_horizon_drifts_without_a_seam"]),
    ("a seam where the tiles meet", "core/placeholders.py",
     "    return [(x, y + lift * i / last) for i, (x, y) in enumerate(line)]",
     "    return [(x, y) for i, (x, y) in enumerate(line)]",
     [f"{T}::test_the_horizon_drifts_without_a_seam"]),
    ("the date back in a grey box", CSS,
     "    width: 3rem;\n    line-height: 1;\n  }",
     "    width: 3rem;\n    line-height: 1;\n    border-radius: var(--radius-sm);\n"
     "    background-color: var(--color-surface-2);\n  }",
     [f"{T}::test_a_row_leads_with_its_date_as_type_not_a_box"]),
    ("a small day", CSS,
     "    font-size: 2rem;\n    font-weight: 700;\n    font-variant-numeric: tabular-nums;",
     "    font-size: 1.375rem;\n    font-weight: 700;\n    font-variant-numeric: tabular-nums;",
     [f"{T}::test_a_row_leads_with_its_date_as_type_not_a_box"]),
    ("the sign-in card outlined and square", CSS,
     "\n  .c-auth {\n",
     "\n  .c-auth {\n    border: 1px solid var(--color-line);\n",
     ["core/tests/test_design_system.py::test_sign_in_is_a_card_beside_what_an_account_is_for"]),
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
