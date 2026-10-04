"""Round 163: break each new guard once and check it goes red (AGENTS.md
rule 7): each mutation takes away what keeps one page's query count flat.
Runs the tests first and stops if they are not green (083).

bash scripts/remote-check.sh run uv run python handoff/rounds/163-query-guards/mutate.py
"""

import os
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
PY = sys.executable
ENV = {**os.environ, "PYTHONUTF8": "1"}

T = "core/tests/test_chapter15_audit.py"


def t(name):
    return f"{T}::{name}"


MUTATIONS = [
    ("news list without its joins", "content/models.py", '            .select_related("category", "author", "cover")\n', "", [t("test_no_n_plus_one_on_the_news_list")]),
    ("homepage without its joins", "content/home.py", '        .select_related("category", "cover", "author")\n', "", [t("test_no_n_plus_one_on_the_homepage")]),
    ("comments without their authors", "comments/services.py", 'page.comments.select_related("author", "reply_to_user"), "author__"', 'page.comments.all(), "author__"', [t("test_no_n_plus_one_under_an_article")]),
    ("search fetches articles twice", "search/services.py", '        .public()\n        .select_related("category")\n', '        .public()\n        .specific()\n        .select_related("category")\n', [t("test_no_n_plus_one_in_search_results")]),
    ("search looks up the site per article", "search/services.py", "            url=page.get_url(request)", "            url=page.get_url()", [t("test_no_n_plus_one_in_search_results")]),
    ("my registrations without joins", "tournaments/registration.py", 'user.individual_signups.select_related(\n            "tournament", "registration", "game_account"\n        ).order_by', "user.individual_signups.order_by", [t("test_no_n_plus_one_in_my_registrations")]),
    ("my scrims without joins", "scrims/views.py", 'request.user.scrim_signups.select_related("scrim", "game_account")', "request.user.scrim_signups.all()", [t("test_no_n_plus_one_in_my_scrims")]),
    ("calendar without its scrims", "core/agenda.py", '        ).select_related("scrim")\n', "        )\n", [t("test_no_n_plus_one_in_the_calendar_feed")]),
    # Taking away select_related("user") here changes nothing: the prefetch
    # below brings the people too (an equivalent mutation, round 163).
    ("team page fetches game IDs per person", "teams/views.py", 'with_avatars(team.memberships.select_related("user"), "user__")\n        .prefetch_related("user__game_accounts")\n', 'with_avatars(team.memberships.select_related("user"), "user__")\n', [t("test_no_n_plus_one_on_a_team_page")]),
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
