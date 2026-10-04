"""Round 159: break each new rule once and check its test goes red (AGENTS.md
rule 7). Runs the tests first and stops if they are not green (083).

bash scripts/remote-check.sh run uv run python handoff/rounds/159-copy-events/mutate.py
"""

import os
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
PY = sys.executable
ENV = {**os.environ, "PYTHONUTF8": "1"}

T = "core/tests/test_copy_events.py"


def t(name):
    return f"{T}::{name}"


MOVES = t("test_how_far_a_copy_moves")
SCRIM = t("test_a_weekly_scrim_is_copied_to_next_week")
CUP = t("test_last_years_tournament_lands_this_year")
MENU = t("test_copy_is_in_the_menu_for_those_who_may_add")
FIELDS = t("test_every_form_field_is_copied_or_moved")
C = "core/services.py"
SS = "scrims/services.py"
TS = "tournaments/services.py"
SH = "scrims/wagtail_hooks.py"
TH = "tournaments/wagtail_hooks.py"

MUTATIONS = [
    ("today counts as ahead", C, "    if earliest + WEEK > now:\n", "    if earliest + WEEK >= now:\n", [MOVES]),
    ("one week short", C, "    return (now - earliest) // WEEK + 1\n", "    return (now - earliest) // WEEK\n", [MOVES, CUP]),
    ("blank times trip it", C, "    filled = [moment for moment in times if moment is not None]\n", "    filled = list(times)\n", [MOVES]),
    ("times stay where they were", C, "        values[name] = moment + shift if moment is not None else None\n", "        values[name] = moment\n", [SCRIM, CUP]),
    ("copy starts from the old row", C, "    return type(original)(**values)\n", "    for name, value in values.items():\n        setattr(original, name, value)\n    original.pk = None\n    return original\n", [SCRIM, CUP]),
    ("scrim close time not moved", SS, 'COPIED_TIMES = ("starts_at", "signup_closes_at")', 'COPIED_TIMES = ("starts_at",)', [SCRIM, FIELDS]),
    ("scrim rule left blank", SS, 'COPIED_FIELDS = ("title", "description", "format", "sjtu_only")', 'COPIED_FIELDS = ("title", "description", "format")', [SCRIM, FIELDS]),
    ("tournament contact left blank", TS, '    "participant_contact",\n)', ")", [CUP, FIELDS]),
    ("tournament status copied too", TS, '    "participant_contact",\n)', '    "participant_contact",\n    "status",\n)', [CUP, FIELDS]),
    ("scrim copy turned off again", SH, "    inspect_view_enabled = True\n", "    copy_view_enabled = False\n    inspect_view_enabled = True\n", [SCRIM, MENU]),
    ("scrim copy is Wagtail's plain one", SH, "    copy_view_class = ScrimCopyView\n", "", [SCRIM]),
    ("scrim copy skips the save steps", SH, "class ScrimCopyView(CopyViewMixin, ScrimCreateView):", "class ScrimCopyView(CopyViewMixin, generic.CreateView):", [SCRIM]),
    ("tournament copy skips the save steps", TH, "class TournamentCopyView(CopyViewMixin, TournamentCreateView):", "class TournamentCopyView(CopyViewMixin, generic.CreateView):", [CUP]),
    ("tournament copy is Wagtail's plain one", TH, "    copy_view_class = TournamentCopyView\n", "", [CUP]),
    ("the manual does not say", "core/admin_manual.py", "每周都有的内战，在上一场的「更多 →", "每周都有的内战，在上一场的「更多", [MENU]),
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
