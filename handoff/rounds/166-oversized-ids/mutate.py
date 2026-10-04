"""Round 166: break each new rule once and check its test goes red (AGENTS.md
rule 7). Runs the tests first and stops if they are not green (083).

bash scripts/remote-check.sh run uv run python handoff/rounds/166-oversized-ids/mutate.py
"""

import os
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
PY = sys.executable
ENV = {**os.environ, "PYTHONUTF8": "1"}

T = "core/tests/test_oversized_ids.py"


def t(name):
    return f"{T}::{name}"


HUGE = t("test_a_huge_article_number_is_not_found")
DATES = t("test_dates_past_any_calendar_get_a_word")
GUARD = t("test_no_address_takes_numbers_of_any_length")

MUTATIONS = [
    ("ids of any length", "core/converters.py", '    regex = "[0-9]{1,18}"\n', '    regex = "[0-9]+"\n', [HUGE]),
    ("the longest id refused", "core/converters.py", '    regex = "[0-9]{1,18}"\n', '    regex = "[0-9]{1,17}"\n', [HUGE]),
    ("comments back on int", "comments/urls.py", '"comments/<id:page_pk>/more/"', '"comments/<int:page_pk>/more/"', [HUGE, GUARD]),
    ("announce back on int", "core/wagtail_hooks.py", '"announce/<str:kind>/<id:pk>/"', '"announce/<str:kind>/<int:pk>/"', [GUARD]),
    ("no date range", "core/activity.py", "    if start < EARLIEST or end > LATEST:\n", "    if False:\n", [DATES]),
    ("1999 allowed", "core/activity.py", "EARLIEST, LATEST = date(2000, 1, 1), date(2100, 12, 31)\n", "EARLIEST, LATEST = date(1999, 1, 1), date(2100, 12, 31)\n", [DATES]),
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
