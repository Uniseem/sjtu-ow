# -*- coding: utf-8 -*-
"""Round 071 mutation checks: break each visibility rule or limit, expect red."""
import io
import os
import shutil
import subprocess
import sys

R = "C:/Users/fyc12/Desktop/Claudee/sjtu-ow/"
ENV = {**os.environ, "PYTHONUTF8": "1"}
T = ["search/tests/test_search.py"]
SVC = "search/services.py"

MUTATIONS = [
    ("未发布文章也搜", SVC,
     "        ArticlePage.objects.live()\n        .public()\n", "        ArticlePage.objects.all()\n"),
    ("草稿和取消的赛事也搜", SVC,
     "    tournaments = Tournament.objects.filter(\n        status__in=[TournamentStatus.PUBLISHED, TournamentStatus.FINISHED]\n    ).order_by(\"-updated_at\", \"-pk\")\n",
     "    tournaments = Tournament.objects.all().order_by(\"-updated_at\", \"-pk\")\n"),
    ("草稿内战也搜", SVC,
     "    scrims = Scrim.objects.filter(\n        status__in=[ScrimStatus.PUBLISHED, ScrimStatus.FINISHED]\n    ).order_by(\"-updated_at\", \"-pk\")\n",
     "    scrims = Scrim.objects.all().order_by(\"-updated_at\", \"-pk\")\n"),
    ("已解散的战队也搜", SVC,
     "    teams = Team.objects.filter(disbanded_at__isnull=True)", "    teams = Team.objects.all()"),
    ("成员不再限于成员页上的人", SVC,
     "    users = joined_users().order_by(\"nickname\", \"pk\")\n",
     "    from accounts.models import User\n\n    users = User.objects.order_by(\"nickname\", \"pk\")\n"),
    ("每类不再截到 20 条", SVC,
     "        if len(hits) > PER_TYPE_LIMIT:\n            return hits[:PER_TYPE_LIMIT], True\n", ""),
    ("只要一个词命中就算", SVC,
     "    return bool(terms) and all(term in folded for term in terms)\n",
     "    return bool(terms) and any(term in folded for term in terms)\n"),
    ("搜索词不再截断", SVC,
     "    text = (raw or \"\").strip()[:MAX_QUERY_LENGTH]\n", "    text = (raw or \"\").strip()\n"),
    ("限流被拆掉", "search/views.py",
     "        if over_limit(f\"search:{client_ip(request)}\", SEARCH_RATE_LIMIT, 60):\n", "        if False:\n"),
]


def clear_caches():
    for app in ("search",):
        for root, dirs, _files in os.walk(R + app):
            for d in list(dirs):
                if d == "__pycache__":
                    shutil.rmtree(os.path.join(root, d), ignore_errors=True)


caught = 0
for label, rel, old, new in MUTATIONS:
    path = R + rel
    original = io.open(path, "rb").read()
    text = original.decode("utf-8")
    norm = text.replace("\r\n", "\n")
    assert norm.count(old) == 1, (label, norm.count(old))
    mutated = norm.replace(old, new)
    if "\r\n" in text:
        mutated = mutated.replace("\n", "\r\n")
    io.open(path, "wb").write(mutated.encode("utf-8"))
    clear_caches()
    try:
        run = subprocess.run(
            [sys.executable, "-m", "uv", "run", "pytest", "-q", "--no-header",
             "-p", "no:cacheprovider", *T],
            cwd=R, env=ENV, capture_output=True, text=True, timeout=600,
        )
    finally:
        io.open(path, "wb").write(original)
        clear_caches()
    summary = [line for line in run.stdout.splitlines() if "passed" in line or "failed" in line or "error" in line]
    hit = run.returncode != 0
    caught += hit
    print(("✓ 被抓到" if hit else "✗ 幸存"), label, "|", summary[-1] if summary else run.stdout[-160:])
print("---")
print(f"{caught}/{len(MUTATIONS)} mutations caught")
