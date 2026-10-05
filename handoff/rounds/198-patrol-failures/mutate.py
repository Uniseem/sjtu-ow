"""Round 198: break each rule once and check its test goes red (AGENTS.md
rule 7). Runs the tests first and stops if they are not green (083).
``--check`` only looks that every mutation still applies.

bash scripts/remote-check.sh run uv run python handoff/rounds/198-patrol-failures/mutate.py

Two mutations (a failure that does not end the round) make the patrol try the
same item again until its minute is up, so they take about a minute each.
"""

import os
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
PY = sys.executable
ENV = {**os.environ, "PYTHONUTF8": "1"}

F = "moderation/tests/test_patrol_failures.py::"
NEVER = F + "test_a_call_that_never_comes_back_is_an_error_not_a_verdict"
PLAIN_400 = F + "test_only_a_plain_400_may_be_the_content"
CUT = F + "test_a_cut_off_answer_is_no_answer"
MALFORMED = F + "test_a_malformed_answer_is_no_answer_but_a_refusal_is_a_verdict"
LEFT_OUT = F + "test_one_left_out_of_a_good_answer_is_to_be_tried_again"
WAITING = F + "test_a_failed_review_leaves_the_item_waiting_with_its_text"
GIVE_UP = F + "test_failures_the_content_may_cause_give_up_at_three"
REUSE = F + "test_a_verdict_the_ai_did_not_give_is_never_reused"
FIRST = F + "test_the_first_failure_ends_the_round"
ALONE = F + "test_an_item_that_failed_goes_alone_after_new_ones"
LONG_ORDER = F + "test_a_long_piece_that_failed_waits_behind_new_ones"
STAYS = F + "test_one_left_out_stays_waiting_while_the_rest_are_read"
BATCH = F + "test_a_batch_is_as_large_as_the_output_limit_holds"
CHUNKS = F + "test_a_long_piece_goes_a_chunk_per_request_and_a_high_risk_ends_it"
MINUTE = F + "test_a_patrol_stops_starting_requests_when_its_minute_is_up"
LONG_MINUTE = F + "test_a_long_piece_waits_for_the_next_go_too"
QUEUED = F + "test_the_rest_is_queued_behind_other_work_and_the_beat_waits"
LETTER = F + "test_while_it_goes_on_the_letter_waits_until_a_finding_is_half_an_hour_old"
HINTS = F + "test_trying_says_what_to_change"
LIST = F + "test_the_review_list_says_what_is_waiting_and_why"
TODO = (
    "core/tests/test_admin_functions.py::"
    "test_the_owner_hears_when_the_ai_cannot_be_reached"
)
CAP = "moderation/tests/test_moderation.py::test_a_patrol_stops_at_the_daily_cap"

MUTATIONS = [
    # --- providers: what counts as no answer
    ("a failed call is a verdict again", "moderation/providers.py",
     '        return failed_result(\n            len(texts), model, f"{FAILED_CALL}{last_error}", counts=counts\n        )',
     '        return unknown_result(len(texts), model, f"{FAILED_CALL}{last_error}")',
     [NEVER]),
    ("every 4xx counts against the content", "moderation/providers.py",
     "                    counts = exc.code == 400", "                    counts = True",
     [PLAIN_400]),
    ("the provider's own words dropped", "moderation/providers.py",
     '    return f"HTTP {exc.code}：{said}" if said else f"HTTP {exc.code}"',
     '    return f"HTTP {exc.code}"', [PLAIN_400]),
    ("a cut-off answer trusted", "moderation/providers.py",
     '        if finish == "length":', "        if False:", [CUT]),
    ("a malformed answer is a verdict", "moderation/providers.py",
     '            return failed_result(\n                count, model, f"输出不符合约定结构：{exc}", counts=True\n            )',
     '            return unknown_result(count, model, f"输出不符合约定结构：{exc}")',
     [MALFORMED]),
    ("an answer about nobody accepted", "moderation/providers.py",
     "        if not by_index.keys() & set(range(count)):", "        if False:",
     [MALFORMED]),
    ("a left-out item taken as read", "moderation/providers.py",
     "index=index, risk=Risk.UNKNOWN, reason=missed, error=missed",
     "index=index, risk=Risk.UNKNOWN, reason=missed", [LEFT_OUT]),
    # --- services: waiting, giving up, reuse, batches
    ("a failure is recorded as read", "moderation/services.py",
     '        item.save(update_fields=["attempts", "last_error", "failed_at"])\n',
     '        item.save(update_fields=["attempts", "last_error", "failed_at"])\n'
     '        record(item, risk=Risk.UNKNOWN, categories=[], reason=error, quote="", model="")\n',
     [WAITING]),
    ("a lost connection counts", "moderation/services.py",
     "        item.attempts += 1 if counts else 0", "        item.attempts += 1",
     [WAITING, GIVE_UP]),
    ("never gives up", "moderation/services.py",
     "        if item.attempts >= GIVE_UP_AFTER:", "        if False:", [GIVE_UP]),
    ("gives up at the first failure", "moderation/services.py",
     "GIVE_UP_AFTER = 3", "GIVE_UP_AFTER = 1", [GIVE_UP]),
    ("a given-up review reused", "moderation/services.py",
     "        .exclude(reason__startswith=GAVE_UP)\n", "", [REUSE]),
    ("an old failed call reused", "moderation/services.py",
     "        .exclude(reason__startswith=FAILED_CALL)\n", "", [REUSE]),
    ("the batch fixed at twenty", "moderation/services.py",
     "    return max(1, min(MAX_BATCH, tokens // TOKENS_PER_ITEM))",
     "    return MAX_BATCH", [BATCH]),
    ("a suspect batched with new ones", "moderation/services.py",
     '    fresh = waiting.filter(attempts=0).order_by("created_at")',
     '    fresh = waiting.order_by("created_at")', [ALONE]),
    ("a lost call sends items alone", "moderation/services.py",
     '    fresh = waiting.filter(attempts=0).order_by("created_at")',
     '    fresh = waiting.filter(failed_at__isnull=True).order_by("created_at")',
     [ALONE]),
    ("suspects in arrival order", "moderation/services.py",
     '    return batch or list(waiting.order_by("attempts", "failed_at", "created_at")[:1])',
     '    return batch or list(waiting.order_by("created_at")[:1])', [ALONE]),
    ("long suspects first", "moderation/services.py",
     '        .order_by("attempts", "failed_at", "created_at")\n    )\n    return list(queryset if limit',
     '        .order_by("created_at")\n    )\n    return list(queryset if limit',
     [LONG_ORDER]),
    ("read items counted as waiting", "moderation/services.py",
     "    queryset = ModerationItem.objects.filter(checked_at__isnull=True)\n    failed =",
     "    queryset = ModerationItem.objects.all()\n    failed =", [TODO, LIST]),
    ("no hint for a cut-off answer", "moderation/services.py",
     "    if TRUNCATED in reason:", "    if False:", [HINTS]),
    ("no hint for a timeout", "moderation/services.py",
     '    if "timed out" in reason.lower():', "    if False:", [HINTS]),
    # --- patrol: stopping, chunks, the minute, the follow-up, the letter
    ("a failed batch does not end the round", "moderation/patrol.py",
     "        services.note_failure(remaining, result.error, counts=result.counts)\n        return FAILED",
     '        services.note_failure(remaining, result.error, counts=result.counts)\n        return ""',
     [FIRST]),
    ("a failed chunk does not end the round", "moderation/patrol.py",
     "            services.note_failure([item], result.error, counts=result.counts)\n            return FAILED",
     '            services.note_failure([item], result.error, counts=result.counts)\n            return ""',
     [WAITING]),
    ("a long piece asked before the cap", "moderation/patrol.py",
     '        return ""\n    if services.quota_left() <= 0:\n        return QUOTA\n    provider = get_provider()',
     '        return ""\n    provider = get_provider()', [CAP]),
    ("every chunk read after a high risk", "moderation/patrol.py",
     "            break  # nothing in the rest can be worse", "            pass", [CHUNKS]),
    ("only the last chunk's tokens", "moderation/patrol.py",
     "        input_tokens += result.input_tokens", "        input_tokens = result.input_tokens",
     [CHUNKS]),
    ("no minute for short batches", "moderation/patrol.py",
     "    while items := services.pending_short_items():\n        if time.monotonic() >= deadline:",
     "    while items := services.pending_short_items():\n        if False:", [MINUTE]),
    ("no minute for long pieces", "moderation/patrol.py",
     "    while items := services.pending_long_items(limit=1):\n        if time.monotonic() >= deadline:",
     "    while items := services.pending_long_items(limit=1):\n        if False:",
     [LONG_MINUTE]),
    ("the rest not queued", "moderation/patrol.py",
     "    if tally.stopped == TIME:\n        follow_up()", "    if tally.stopped == TIME:\n        pass",
     [QUEUED]),
    ("queued after any stop", "moderation/patrol.py",
     "    if tally.stopped == TIME:", "    if tally.stopped:", [QUEUED]),
    ("the follow-up ahead of other work", "moderation/patrol.py",
     "    patrol.using(priority=FOLLOW_UP_PRIORITY).enqueue()", "    patrol.enqueue()",
     [QUEUED]),
    ("the beat queues a second round", "moderation/patrol.py",
     "    cache.set(PATROL_KEY, timezone.now().isoformat(), PATROL_MINUTES * 60)\n    patrol.using",
     "    patrol.using", [QUEUED]),
    ("the letter held for good", "moderation/patrol.py",
     "        if not letter_overdue():", "        if True:", [LETTER]),
    ("the letter not held", "moderation/patrol.py",
     "        if not letter_overdue():", "        if False:", [LETTER]),
    # --- where it shows
    ("the to-do points at the review list", "core/admin_todo.py",
     "                _settings_url(SiteSettings.load()),\n                stuck,",
     '                reverse("moderation_index"),\n                stuck,', [TODO]),
    ("the to-do nags with the review off", "core/admin_todo.py",
     '    if not services.is_enabled():\n        return 0, ""\n', "", [TODO]),
    ("the list keeps quiet about failures", "moderation/templates/moderation/index.html",
     "  {% if failed %}", "  {% if False %}", [LIST]),
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
