"""Round 181: the soft refusals the sweep found untested, each broken once
(condition replaced by False) to check the test added for it goes red
(AGENTS.md rule 7). Runs the tests first and stops if they are not green (083).

bash scripts/remote-check.sh run uv run python handoff/rounds/181-soft-guards/mutate.py
"""

import os
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
PY = sys.executable
ENV = {**os.environ, "PYTHONUTF8": "1"}

C = "core/tests/test_soft_guards.py::"
ACTION = C + "test_an_unknown_handling_is_refused_not_a_crash"
SCAN = C + "test_no_full_scan_while_moderation_is_off"
PRERENDER = C + "test_rebuilding_says_so_while_prerendering_is_off"
FONT = C + "test_a_weight_with_nothing_to_download"
ADDLIMIT = C + "test_the_add_form_is_not_offered_at_the_limit"
OUTGREW = C + "test_editing_a_tournament_the_teams_outgrew_warns"
T = "teams/tests/test_teams.py::"
CREATE = T + "test_create_is_rate_limited"
APPLY = T + "test_applications_are_rate_limited"
NAME = T + "test_a_taken_name_is_marked_on_the_name_field"

MV = "moderation/admin_views.py"
TV = "teams/views.py"

MUTATIONS = [
    ("add form offered at the limit", "accounts/views.py", "        if form and at_limit:\n", "        if False:\n", [ADDLIMIT]),
    ("empty zip downloaded", "core/fonts/admin_views.py", "    if not face.slices:\n", "    if False:\n", [FONT]),
    ("rebuild queued while off", "core/prerender_admin.py", "    if not prerender.is_enabled():\n", "    if False:\n", [PRERENDER]),
    ("unknown handling accepted", MV, "    if action not in ACTIONS:\n", "    if False:\n", [ACTION]),
    ("scan while moderation off", MV, "    if not services.is_enabled():\n", "    if False:\n", [SCAN]),
    ("teams created without limit", TV, '        if over_limit(f"team_create:{request.user.pk}", CREATE_LIMIT, DAY):\n', "        if False:\n", [CREATE]),
    ("taken name as a toast", TV, "    if str(exc) == services.NAME_TAKEN:\n", "    if False:\n", [NAME]),
    ("applications without limit", TV, '        elif over_limit(f"team_apply:{request.user.pk}", APPLY_LIMIT, DAY):\n', "        elif False:\n", [APPLY]),
    ("outgrown tournament saved quietly", "tournaments/wagtail_hooks.py", "        warning = services.roster_min_warning(instance)\n        if warning:\n", "        warning = services.roster_min_warning(instance)\n        if False:\n", [OUTGREW]),
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
