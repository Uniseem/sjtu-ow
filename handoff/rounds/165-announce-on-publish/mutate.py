"""Round 165: break each new rule once and check its test goes red (AGENTS.md
rule 7). Runs the tests first and stops if they are not green (083).

bash scripts/remote-check.sh run uv run python handoff/rounds/165-announce-on-publish/mutate.py
"""

import os
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
PY = sys.executable
ENV = {**os.environ, "PYTHONUTF8": "1"}

T = "core/tests/test_announcements.py"


def t(name):
    return f"{T}::{name}"


PLANNED = t("test_a_planned_article_is_announced_when_it_goes_live")
BY_HAND = t("test_publishing_a_planned_article_by_hand_sends_it_too")
DRAFTS = t("test_drafts_and_other_roles_cannot_announce_articles")
S = "core/services.py"

MUTATIONS = [
    ("planned articles refused", S, "        and going_live_at(kind, obj) is None\n", "", [PLANNED, BY_HAND]),
    ("drafts count as planned", S, '    planned = (\n        obj.revisions.filter(approved_go_live_at__isnull=False)\n        .order_by("-approved_go_live_at")\n        .first()\n    )\n    return planned.approved_go_live_at if planned else None\n', '    planned = obj.revisions.order_by("-created_at").first()\n    return planned.created_at if planned else None\n', [DRAFTS]),
    ("sent at once", S, "    if not waiting:\n        transaction.on_commit(lambda: send_broadcast.enqueue(broadcast.pk))\n", "    transaction.on_commit(lambda: send_broadcast.enqueue(broadcast.pk))\n", [PLANNED, BY_HAND]),
    ("counted when planned", S, "                recipient_count=0 if waiting else recipient_count(obj),\n", "                recipient_count=recipient_count(obj),\n", [PLANNED]),
    ("planned twice", S, "    if done is not None and done.waits_for_publish:\n        return \"已经安排在上线时通知全体成员，同一篇只发一次。\"\n", "", [PLANNED]),
    ("never sent on publish", "content/signals.py", '        send_waiting("article", instance)\n', "        pass\n", [PLANNED, BY_HAND]),
    ("sent again on every publish", S, "        kind=kind, object_id=obj.pk, waits_for_publish=True\n", "        kind=kind, object_id=obj.pk\n", [BY_HAND]),
    ("count kept from planning", S, "    if not waiting.update(\n        waits_for_publish=False, recipient_count=recipient_count(obj)\n    ):", "    if not waiting.update(waits_for_publish=False):", [PLANNED]),
    ("no button for planned articles", "content/wagtail_hooks.py", "    if not (page.live or planned):\n", "    if not page.live:\n", [PLANNED]),
    ("button says send now", "content/wagtail_hooks.py", "    item_class = AnnounceArticleItem if page.live else AnnounceArticleOnPublishItem\n", "    item_class = AnnounceArticleItem\n", [PLANNED]),
    ("preview without the time", "core/templates/core/admin/announce.html", '{{ going_live_at|date:"n 月 j 日 H:i" }} 上线', "稍后上线", [PLANNED]),
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
