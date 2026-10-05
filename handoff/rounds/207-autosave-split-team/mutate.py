"""Round 207: break each rule once and check its test goes red (AGENTS.md
rule 7). Runs the tests first and stops if they are not green (083).
``--check`` only looks that every mutation still applies.

bash scripts/remote-check.sh run uv run python handoff/rounds/207-autosave-split-team/mutate.py
"""

import os
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
PY = sys.executable
ENV = {**os.environ, "PYTHONUTF8": "1"}

S = "core/tests/test_autosave_split_team.py::"
UNTICK = S + "test_unticking_saves_and_takes_the_player_off_the_board"
MOVE = S + "test_a_move_saves_and_the_copy_text_follows"
LOG = S + "test_each_kind_of_edit_is_one_log_entry"
TELLS = S + "test_a_move_on_the_board_tells_the_form"
NAME = S + "test_a_taken_name_is_kept_and_the_rest_saved"
LOGO = S + "test_a_chosen_logo_goes_up_at_once_and_only_once"

MUTATIONS = [
    ("a tick not saved", "scrims/split_admin.py",
     '        services.set_selection(scrim=scrim, signup_ids=request.POST.getlist("signups"))\n'
     '        autosave.log_edit(scrim, request.user, action="scrims.select")',
     '        autosave.log_edit(scrim, request.user, action="scrims.select")', [UNTICK]),
    ("the board not sent back", "scrims/split_admin.py",
     '        outcome.replace["[data-split-board]"] = render_to_string(',
     '        outcome.replace["[data-elsewhere]"] = render_to_string(', [UNTICK]),
    ("a move not saved", "scrims/split_admin.py",
     "        services.save_teams(\n            scrim=scrim, placements=_placements_from_post(request, scrim)\n        )",
     "        pass", [MOVE]),
    ("the copy text not sent back", "scrims/split_admin.py",
     '        outcome.replace["[data-split-copy]"] = render_to_string(',
     '        outcome.replace["[data-elsewhere]"] = render_to_string(', [MOVE]),
    ("every tick logged", "scrims/split_admin.py",
     '        autosave.log_edit(scrim, request.user, action="scrims.select")',
     '        admin_log.record(scrim, "scrims.select", request.user)', [LOG]),
    ("every move logged", "scrims/split_admin.py",
     '        autosave.log_edit(scrim, request.user, action="scrims.save_teams")',
     '        admin_log.record(scrim, "scrims.save_teams", request.user)', [LOG]),
    ("a move tells nobody", "static/js/scrim-split.js",
     '        marker.dispatchEvent(new Event("change", { bubbles: true }));',
     "        void marker;", [TELLS]),
    ("a taken name goes to the service", "teams/forms.py",
     "        if name_taken(name, exclude_pk=self.instance.pk):\n            raise forms.ValidationError(NAME_TAKEN)\n",
     "", [NAME]),
    ("the file box kept", "teams/views.py",
     '        outcome.values = {"logo_file": "", "remove_logo": False}\n', "", [LOGO]),
    ("the logo not shown", "teams/views.py",
     '        outcome.replace["[data-team-logo]"] = render_to_string(',
     '        outcome.replace["[data-elsewhere]"] = render_to_string(', [LOGO]),
    ("「删除队标」 ignored", "teams/views.py",
     '    if "remove_logo" in names and form.cleaned_data.get("remove_logo"):\n        logo = None\n',
     "", [LOGO]),
    ("a chosen logo waits for 保存", "teams/views.py",
     '    if "logo_file" in names and form.cleaned_data.get("logo_file"):',
     "    if False:", [LOGO]),
]


def run(tests):
    return subprocess.run(
        [PY, "-m", "pytest", "-q", "-x", "-p", "no:cacheprovider", *tests],
        cwd=ROOT,
        env=ENV,
        capture_output=True,
        text=True,
    ).returncode


def _text(rel):
    return (ROOT / rel).read_bytes().decode("utf-8").replace("\r\n", "\n")


def check():
    bad = [
        (label, _text(rel).count(old))
        for label, rel, old, _new, _tests in MUTATIONS
        if _text(rel).count(old) != 1
    ]
    print("mutations:", len(MUTATIONS), "not applying:", bad or "none")
    return not bad


def main():
    if not check():
        sys.exit(1)
    if "--check" in sys.argv:
        return
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
            text = raw.replace("\r\n", "\n").replace(old, new)
            path.write_bytes(
                (text.replace("\n", "\r\n") if crlf else text).encode("utf-8")
            )
            for test in tests:
                red = run([test]) != 0
                print(("caught " if red else "MISSED ") + label + " -> " + test.split("::")[1])
                if not red:
                    failed.append((label, test))
        finally:
            shutil.copy2(backup, path)
            backup.unlink()
            folder = rel.rsplit("/", 1)[0]
            for cache in ROOT.glob(folder + "/**/__pycache__/*.pyc"):
                cache.unlink()
    assert run(every) == 0, "not green after restoring"
    print("restored and green;", "missed:", failed or "none")


if __name__ == "__main__":
    main()
