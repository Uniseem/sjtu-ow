"""Round 143: break each new rule once and check its test goes red (AGENTS.md
rule 7). Runs the tests first and stops if they are not green (083).

bash scripts/remote-check.sh run uv run python handoff/rounds/143-card-dates/mutate.py
"""

import os
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
PY = sys.executable
ENV = {**os.environ, "PYTHONUTF8": "1"}

CARDS = "core/tests/test_arena_pages.py::test_open_and_upcoming_cards_say_when_they_play"
HOME = "content/tests/test_home_sections.py::test_the_feature_card_says_when_they_play"
CARD = "templates/components/tournament_card.html"
WHEN = '{% if tournament.starts_at %}<span data-card-starts>{{ tournament.starts_at|ow_md }} 比赛</span>{% endif %}'

MUTATIONS = [
    ("open cards leave the date out", CARD, " 截止</span>" + WHEN, " 截止</span>", [CARDS]),
    ("upcoming cards leave the date out", CARD, " 开放</span>" + WHEN, " 开放</span>", [CARDS]),
    ("a date line even without a date", CARD,
     " 截止</span>" + WHEN,
     ' 截止</span><span data-card-starts>{{ tournament.starts_at|ow_md }} 比赛</span>',
     [CARDS]),
    ("the homepage card leaves it out", "content/templates/content/home_page.html",
     "{% if feature.tournament.starts_at %} · {{ feature.tournament.starts_at|ow_md }} 比赛{% endif %}",
     "", [HOME]),
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
