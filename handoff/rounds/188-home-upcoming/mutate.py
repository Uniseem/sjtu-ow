"""Round 188: break each new rule once and check its test goes red (AGENTS.md
rule 7). Runs the tests first and stops if they are not green (083).

bash scripts/remote-check.sh run uv run python handoff/rounds/188-home-upcoming/mutate.py
"""

import os
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
PY = sys.executable
ENV = {**os.environ, "PYTHONUTF8": "1"}

H = "content/tests/test_home_sections.py::"
BOTH = H + "test_an_empty_agenda_keeps_both_places"
ROWS = H + "test_scrim_rows_keep_the_first_five_by_start"
LITTLE = H + "test_every_block_keeps_its_places_when_there_is_little"
EMPTY = H + "test_an_empty_homepage_says_so_in_the_first_place_of_each"
S = "scrims/tests/test_home_listing.py::"
FIVE = S + "test_the_homepage_lists_the_next_five_however_far_off"
REFRESH = S + "test_the_homepage_is_refreshed_when_the_scrim_closes_and_starts"
T = "tournaments/tests/test_public_pages.py::"
NONE = T + "test_the_homepage_says_so_when_there_is_no_tournament"
NEXT = T + "test_without_one_open_the_next_one_not_over_is_shown"
LAST = T + "test_when_all_are_over_the_last_one_is_shown"
TPL = "content/templates/content/home_page.html"
HOME = "content/home.py"
SV = "scrims/services.py"

MUTATIONS = [
    ("columns follow the content again", TPL, '<div class="c-upcoming c-upcoming--two">', '<div class="c-upcoming">', [BOTH]),
    ("no empty card", TPL, '            <p class="c-feature__title">还没有赛事</p>\n', "", [BOTH, NONE]),
    ("four scrims", SV, "HOME_SCRIM_COUNT = 5\n", "HOME_SCRIM_COUNT = 4\n", [FIVE]),
    ("four rows", HOME, "SCRIM_ROW_COUNT = 5\n", "SCRIM_ROW_COUNT = 4\n", [ROWS]),
    ("the 7-day window back", SV, "            starts_at__gte=now,\n        ).order_by", "            starts_at__gte=now,\n            starts_at__lte=now + timedelta(days=7),\n        ).order_by", [FIVE]),
    ("only open tournaments", HOME, '    elif by_phase.get("upcoming") or by_phase.get("closed"):\n', "    elif False:\n", [NEXT]),
    ("the furthest one ahead", HOME, "        chosen = min(ahead, key=_when)\n", "        chosen = max(ahead, key=_when)\n", [NEXT]),
    ("the first finished one", HOME, '        chosen = max(by_phase["finished"], key=_when)\n', '        chosen = min(by_phase["finished"], key=_when)\n', [LAST]),
    ("finished ones never offered", HOME, "    return found + ([last] if last else [])\n", "    return found\n", [LAST]),
    ("wrong badge before registration", TPL, '<span class="c-status c-status--info">即将开始报名</span>', '<span class="c-status c-status--info">报名中</span>', [NEXT]),
    ("scrim list shrinks", HOME, '        "scrim_blanks": blanks(rows, SCRIM_ROW_COUNT),\n', '        "scrim_blanks": range(0),\n', [LITTLE, EMPTY]),
    ("news grid shrinks", HOME, '        "news_blanks": blanks(news, LATEST_ARTICLE_COUNT),\n', '        "news_blanks": range(0),\n', [LITTLE, EMPTY]),
    ("notices shrink", HOME, '        "notice_blanks": blanks(notice_rows, NOTICE_COUNT),\n', '        "notice_blanks": range(0),\n', [LITTLE, EMPTY]),
    ("teams shrink", HOME, '        "team_blanks": blanks(home_teams, HOME_TEAM_COUNT),\n', '        "team_blanks": range(0),\n', [LITTLE]),
    ("every empty card says it", TPL, '{% if forloop.first and not news %}还没有文章{% endif %}', "还没有文章", [EMPTY]),
    ("news columns follow the window", TPL, '<div class="c-media-grid c-media-grid--two">', '<div class="c-media-grid">', [LITTLE, EMPTY]),
    ("homepage refreshed 7 days ahead again", SV, "    runs = [(scrim.signup_deadline, status_pages), (scrim.starts_at, status_pages)]\n", '    runs = [(scrim.starts_at - timedelta(days=7), ["/"]), (scrim.signup_deadline, status_pages), (scrim.starts_at, status_pages)]\n', [REFRESH]),
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
