"""Round 194: break each rule once and check its test goes red (AGENTS.md
rule 7). Runs the tests first and stops if they are not green (083).

bash scripts/remote-check.sh run uv run python handoff/rounds/194-ai-patrol/mutate.py
"""

import os
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
PY = sys.executable
ENV = {**os.environ, "PYTHONUTF8": "1"}

M = "moderation/tests/test_moderation.py::"
SAVE = M + "test_saving_puts_content_on_record_without_calling_the_ai"
WHOLE = M + "test_a_patrol_reads_long_pieces_whole_and_then_forgets_them"
CAP = M + "test_a_patrol_stops_at_the_daily_cap"
LETTER = M + "test_one_letter_lists_what_a_patrol_found"
ADDRESS = M + "test_the_letter_goes_to_the_address_set_in_the_settings"
UNKNOWN = M + "test_unreadable_is_not_a_finding_and_nothing_is_mailed_on_its_own"
HALF_HOUR = M + "test_the_worker_queues_a_patrol_at_most_every_half_hour"
BEAT = M + "test_the_workers_beat_queues_the_patrol"
PAGE = "core/tests/test_admin_functions.py::test_the_record_page_has_no_scan_button_and_says_how_alerts_come"
P = "moderation/patrol.py"
N = "moderation/notifications.py"

MUTATIONS = [
    ("long text not kept", "moderation/services.py", '"full_text": "" if target_type in SHORT_TYPES else text,', '"full_text": "",', [SAVE, WHOLE]),
    ("full text kept for ever", "moderation/services.py", '    item.full_text = ""\n', "", [WHOLE]),
    ("the patrol reads only the excerpt", P, "services.split_text(item.full_text or item.excerpt)", "services.split_text(item.excerpt)", [WHOLE]),
    ("long pieces past the cap", P, "    if services.quota_left() <= 0:\n        return False\n    chunks", "    chunks", [CAP]),
    ("unreadable counts as a finding", P, "DOUBTFUL = (Risk.LOW, Risk.MEDIUM, Risk.HIGH)", "DOUBTFUL = (Risk.LOW, Risk.MEDIUM, Risk.HIGH, Risk.UNKNOWN)", [UNKNOWN]),
    ("a patrol every beat", P, "    if not cache.add(PATROL_KEY, timezone.now().isoformat(), PATROL_MINUTES * 60):", "    if False:", [HALF_HOUR]),
    ("the setting ignored", N, "    if address:", "    if False:", [ADDRESS]),
    ("an empty letter", N, "    items = list(doubtful_unsent())\n    if not items:\n        return 0\n", "    items = list(doubtful_unsent())\n", [LETTER]),
    ("told again and again", N, "        notified_at=timezone.now()\n", "        notified_at=None\n", [LETTER]),
    ("the beat forgets the patrol", "core/worker.py", '        (enqueue_if_due, "queue the AI patrol"),\n', "", [BEAT]),
    ("the page keeps quiet about the mail", "moderation/templates/moderation/index.html", "AI 每 30 分钟巡查一次", "AI 会巡查", [PAGE]),
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
