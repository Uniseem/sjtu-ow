"""217 复核 16（测试质量）：一次基线，跑三组变异。

1. 硬守卫：210 普查（results.jsonl）之后新出现的「if 条件: 拒绝」
2. 软守卫：181 普查之后新出现的「if 条件: messages.error / add_error」
   （181 时还没有 backoffice/，196 起后台的软拒绝从没扫过）
3. 16-mutate.py 里手挑的变异（隐私过滤、CSP、限流、211 的字段……）

都在 git archive 出来的独立副本里改（210 mutate_guards.py 的 make_copy），先跑所在
应用的测试，全绿再跑全量，全量也绿才算 survived。

AGENTS「硬规则 7」：长的普查在测试机上单独开工作树后台跑，别占 remote-check.sh 的锁。
    nice -n 10 .venv/bin/python handoff/rounds/217-second-review/findings/16-sweep.py --workers 3
"""

import argparse
import importlib.util
import json
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

ROOT = Path(__file__).resolve().parents[4]
HERE = Path(__file__).resolve().parent


def _load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


mg = _load("mg", ROOT / "handoff/rounds/210-full-review/mutate_guards.py")
manual = _load("manual", HERE / "16-mutate.py")


def done_in(path):
    rows = [json.loads(line) for line in path.read_text().splitlines() if line.strip()]
    return {(r["file"], r["function"], r["condition"]) for r in rows}


def jobs():
    out = []
    hard_done = done_in(ROOT / "handoff/rounds/210-full-review/results.jsonl")
    soft_done = done_in(ROOT / "handoff/rounds/181-soft-guards/results.jsonl")
    for path in mg.targets():
        for guard in mg.find_guards(path):
            if (guard["file"], guard["function"], guard["condition"]) not in hard_done:
                out.append(("hard", guard))
        for guard in mg.find_guards(path, soft=True):
            if (guard["file"], guard["function"], guard["condition"]) not in soft_done:
                out.append(("soft", guard))
    for mutation in manual.MUTATIONS:
        out.append(("manual", mutation))
    return out


def run_guard(copy, guard):
    target = copy / guard["file"]
    original = target.read_text()
    target.write_text(mg.mutate(original, guard["span"]))
    try:
        tests = mg.test_dir_for(guard["file"])
        code, failed, tail = mg.pytest(copy, tests) if tests else (0, [], "")
        stage = "app"
        if code == 0:
            code, failed, tail = mg.pytest(copy)
            stage = "full"
    finally:
        target.write_text(original)
    result = "caught" if code == 1 else "survived" if code == 0 else f"error({code})"
    return {
        "label": f"{guard['file']}:{guard['line']} {guard['function']} if {guard['condition'][:80]}",
        "result": result,
        "stage": stage,
        "failed": failed[:2],
        "tail": tail,
    }


def run_manual(copy, mutation):
    row = manual.run_one(copy, mutation)
    row["label"] = f"{row['key']} {row['name']}"
    return row


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--workers", type=int, default=3)
    parser.add_argument("--list", action="store_true")
    parser.add_argument("--out", type=Path, default=Path("/tmp/sjtu-ow-217-16/sweep.jsonl"))
    args = parser.parse_args()
    todo = jobs()
    if args.list:
        for kind, item in todo:
            label = (
                f"{item['file']}:{item['line']} {item['function']} if {item['condition'][:80]}"
                if kind != "manual"
                else f"{item[0]} {item[1]}"
            )
            print(kind, label)
        print(len(todo), "个")
        return
    args.out.parent.mkdir(parents=True, exist_ok=True)
    copies = [args.out.parent / "sweep-copies" / f"w{i}" for i in range(args.workers)]
    for copy in copies:
        mg.make_copy(copy)
    print(f"{len(todo)} 个变异。基线（并行，未变异）：", flush=True)
    with ThreadPoolExecutor(args.workers) as pool:
        baselines = list(pool.map(lambda c: mg.pytest(c), copies))
    for copy, (code, failed, tail) in zip(copies, baselines, strict=True):
        print(f"  {copy.name}: exit={code} {tail} {failed}", flush=True)
    if any(code != 0 for code, _, _ in baselines):
        print("基线不绿，停下（083 的教训）。")
        return
    free = list(copies)
    lock = threading.Lock()

    def work(job):
        kind, item = job
        with lock:
            copy = free.pop()
        started = time.monotonic()
        try:
            row = run_guard(copy, item) if kind != "manual" else run_manual(copy, item)
        finally:
            with lock:
                free.append(copy)
        row["kind"] = kind
        row["seconds"] = round(time.monotonic() - started, 1)
        return row

    count = 0
    with args.out.open("w") as out, ThreadPoolExecutor(args.workers) as pool:
        for row in pool.map(work, todo):
            count += 1
            out.write(json.dumps(row, ensure_ascii=False) + "\n")
            out.flush()
            mark = {"caught": "ok", "survived": "!!"}.get(row["result"], "??")
            print(
                f"[{count}/{len(todo)}] {mark} {row['kind']} {row['label']}：{row['result']}"
                f"（{row['stage']}）{row['failed'][:1]} {row['tail']}",
                flush=True,
            )
    print("完成", flush=True)


if __name__ == "__main__":
    main()
