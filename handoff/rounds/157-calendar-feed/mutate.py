"""Round 157: break each new rule once and check its test goes red (AGENTS.md
rule 7). Runs the tests first and stops if they are not green (083).

bash scripts/remote-check.sh run uv run python handoff/rounds/157-calendar-feed/mutate.py
"""

import os
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
PY = sys.executable
ENV = {**os.environ, "PYTHONUTF8": "1"}

T = "core/tests/test_calendar_feed.py"


def t(name):
    return f"{T}::{name}"


EVENTS = t("test_my_scrims_become_calendar_events")
F = "core/calendar_feed.py"

MUTATIONS = [
    ("scrims last two hours", F, '"内战": timedelta(hours=3)', '"内战": timedelta(hours=2)', [EVENTS]),
    ("undated events go in", F, "        if item.when is None:\n            continue", "        if False:\n            continue", [EVENTS]),
    ("no team in the description", F,
     "            f\"DESCRIPTION:{_escape(f'{item.note}\\n{url}')}\",\n",
     "            f\"DESCRIPTION:{_escape(url)}\",\n", [EVENTS]),
    ("commas left as they are", F, '        .replace(",", "\\\\,")\n', "", [t("test_text_is_escaped")]),
    ("long lines not folded", F, '    return "\\r\\n".join(_fold(line) for line in lines) + "\\r\\n"',
     '    return "\\r\\n".join(lines) + "\\r\\n"', [EVENTS]),
    ("folds split characters", F, "        width = len(char.encode())", "        width = 1",
     [t("test_long_lines_are_folded_without_splitting_characters")]),
    ("deactivated accounts keep their calendar", F,
     "    return User.objects.filter(pk=pk, is_active=True).first()\n",
     "    return User.objects.filter(pk=pk).first()\n", [t("test_a_bad_or_dead_address_is_not_found")]),
    ("no rate limit", "core/views.py",
     '    if over_limit(f"calendar:{client_ip(request)}", CALENDAR_RATE_LIMIT):\n',
     "    if False:\n", [t("test_hammering_the_feed_is_limited")]),
    ("the page does not offer it", "templates/me/registrations.html",
     '      <a href="{{ calendar_webcal }}" class="c-btn c-btn--secondary">', '      <a href="" class="c-btn c-btn--secondary">',
     [t("test_my_registrations_page_offers_it")]),
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
