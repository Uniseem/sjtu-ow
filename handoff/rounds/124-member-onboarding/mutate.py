"""Round 124: break each new rule once and check its test goes red (AGENTS.md
rule 7). Runs the tests first and stops if they are not green (083).

uv run python handoff/rounds/124-member-onboarding/mutate.py
"""

import os
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
PY = sys.executable
ENV = {**os.environ, "PYTHONUTF8": "1"}

T = "accounts/tests/test_onboarding.py"


def t(name):
    return f"{T}::{name}"


MUTATIONS = [
    ("new members land on the homepage", "accounts/adapter.py",
     '        return reverse("me_profile")\n', '        return "/"\n',
     [t("test_a_new_member_lands_on_their_profile_with_what_to_do")]),
    ("no welcome", "accounts/adapter.py",
     "        messages.success(\n            request,\n            \"欢迎加入社区！",
     "        (lambda *a: None)(\n            request,\n            \"欢迎加入社区！",
     [t("test_a_new_member_lands_on_their_profile_with_what_to_do")]),
    ("the tournament notice has no links", "tournaments/templates/tournaments/slots/actions.html",
     '          </ul>\n          {% include "components/profile_gap_links.html" %}\n', "          </ul>\n",
     [t("test_the_tournament_notice_links_to_what_is_missing")]),
    ("the tournament slot computes no gaps", "tournaments/slots.py",
     '        "profile_gaps": _gaps(user) if individual_problems else [],\n',
     '        "profile_gaps": [],\n',
     [t("test_the_tournament_notice_links_to_what_is_missing")]),
    ("the team notice has no link", "teams/templates/teams/slots/join.html",
     '{{ apply_reason }}{% include "components/profile_gap_links.html" %}', "{{ apply_reason }}",
     [t("test_the_team_notice_links_to_adding_a_game_id")]),
    ("the team page passes no gaps", "teams/views.py",
     '            "profile_gaps": join_gaps(request.user, can_apply),\n', "",
     [t("test_the_team_notice_links_to_adding_a_game_id")]),
    ("the team fragment passes no gaps", "teams/slots.py",
     '            "profile_gaps": join_gaps(request.user, can_apply),\n', "",
     [t("test_the_team_notice_links_to_adding_a_game_id")]),
    ("nobody gets the guide", "content/models.py",
     '        SubmissionGuidePanel(heading="投稿须知"),\n', "",
     [t("test_submitters_get_the_guide_and_editors_do_not")]),
    ("editors get the guide too", "content/permissions.py",
     "    return _group_names(user).isdisjoint({GROUP_CONTENT, GROUP_AUTHOR})\n",
     "    return True\n",
     [t("test_submitters_get_the_guide_and_editors_do_not")]),
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
