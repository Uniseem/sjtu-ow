"""Round 190: break each rule once and check its test goes red (AGENTS.md
rule 7). Runs the tests first and stops if they are not green (083).

bash scripts/remote-check.sh run uv run python handoff/rounds/190-home-no-placeholders/mutate.py
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
EMPTY = H + "test_an_empty_agenda_keeps_its_place_and_shows_nothing"
LITTLE = H + "test_every_block_shows_only_what_there_is"
COLUMN = H + "test_the_scrims_keep_the_right_column_without_a_tournament"
NO_CARD = "tournaments/tests/test_public_pages.py::test_the_homepage_leaves_the_card_out_when_there_is_no_tournament"
TPL = "content/templates/content/home_page.html"
CSS = "assets/css/input.css"

MUTATIONS = [
    ("columns follow the content again", TPL, '<div class="c-upcoming c-upcoming--two">', '<div class="c-upcoming">', [EMPTY, LITTLE]),
    ("the list drifts left", CSS, "    .c-upcoming--two > .c-rows {\n      grid-column: 2;\n    }", "    .c-upcoming--two > .c-rows {\n    }", [COLUMN]),
    ("the card leaves its column", CSS, "      grid-column: 1;\n      aspect-ratio: auto;", "      aspect-ratio: auto;", [COLUMN]),
    ("news columns follow the window", TPL, '<div class="c-media-grid c-media-grid--two">', '<div class="c-media-grid">', [LITTLE]),
    ("team tiles stretch", TPL, '<ul class="c-teams c-teams--six">', '<ul class="c-teams">', [LITTLE]),
    ("an empty team list drawn", TPL, "    {% if home_teams %}\n    <ul", "    {% if True %}\n    <ul", [LITTLE]),
    ("an empty card again", TPL, "        {% endwith %}\n      {% endif %}\n", '        {% endwith %}\n      {% else %}<div class="c-feature c-feature--empty"><p class="c-feature__title">还没有赛事</p></div>\n      {% endif %}\n', [EMPTY, NO_CARD]),
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
