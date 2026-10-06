#!/usr/bin/env bash
# 217 复核 16（测试质量）：只跑 210 普查之后新出现的守卫。
# 硬守卫：210 的 results.jsonl 里没有的（按文件、函数、条件匹配）。
# 软守卫：181 的 results.jsonl 里没有的（181 时还没有 backoffice/，196 起的软拒绝从没扫过）。
# 用 210 的 mutate_guards.py（它在独立的 git archive 副本里改，不碰仓库工作区）。
#   bash scripts/remote-check.sh run bash handoff/rounds/217-second-review/findings/16-sweep.sh
set -u
S=handoff/rounds/210-full-review/mutate_guards.py
OUT=/tmp/sjtu-ow-217-16
mkdir -p "$OUT"
echo "== 硬守卫（210 之后新增）"
.venv/bin/python "$S" --workers 4 --copies "$OUT/copies" --out "$OUT/hard.jsonl" \
  --resume handoff/rounds/210-full-review/results.jsonl
echo "== 软守卫（181 之后新增，含全部 backoffice）"
.venv/bin/python "$S" --soft --workers 4 --copies "$OUT/copies" --out "$OUT/soft.jsonl" \
  --resume handoff/rounds/181-soft-guards/results.jsonl
echo "== 结果"
for f in hard soft; do
  echo "-- $f"
  .venv/bin/python - "$OUT/$f.jsonl" <<'PY'
import json, sys
rows = [json.loads(l) for l in open(sys.argv[1])]
for r in rows:
    print(r["result"], r["stage"], f'{r["file"]}:{r["line"]}', r["function"], "if", r["condition"][:90], "|", (r["failed"] or [""])[0], "|", r["tail"])
print(len(rows), "rows;", sum(r["result"] == "survived" for r in rows), "survived")
PY
done
