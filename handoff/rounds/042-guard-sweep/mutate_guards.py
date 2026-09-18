"""Remove every "if condition: refuse" guard, one at a time, and run the tests.

A guard is an ``if`` whose direct body raises, appends to ``problems`` /
``errors`` (registration collects problems and raises once), or returns a
refusal (login redirect, forbidden, or any response with a 4xx status). Each mutant
replaces the condition with ``False``. The app's own tests run first; a
survivor is re-run against the full suite.

Every result is reported by file, line, enclosing function and the original
condition's source — never by a name someone made up for it (round 041).

Runs in N exported copies of the repository so mutants never touch the real
checkout, each copy with its own test database.

    python handoff/rounds/042-guard-sweep/mutate_guards.py --list
    python handoff/rounds/042-guard-sweep/mutate_guards.py --workers 5 --out r.jsonl
"""

import argparse
import ast
import json
import os
import re
import shutil
import subprocess
import sys
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

REPO = Path(__file__).resolve().parents[3]
PYTHON = REPO / ".venv" / "bin" / "python"
GIT = os.environ.get("GIT", "git")

APPS = [
    "accounts",
    "content",
    "core",
    "integrations",
    "lfg",
    "moderation",
    "scrims",
    "sjtu_ow",
    "teams",
    "tournaments",
]


def targets() -> list[str]:
    """Every source file of every app. Hand-picking files is how guards get missed."""
    found = []
    for app in APPS:
        for path in sorted((REPO / app).rglob("*.py")):
            rel = path.relative_to(REPO)
            if {"tests", "migrations", "__pycache__"} & set(rel.parts):
                continue
            found.append(str(rel))
    return found


COLLECTORS = {"problems", "errors"}

# Wall-clock assertions. Under parallel load they fail at random, and a random
# failure reads as "mutant caught" — hiding exactly the survivors this looks
# for. The first run's baseline showed it: 6v6 teaming took over a second.
TIMING_TESTS = [
    "scrims/tests/test_teaming.py::test_6v6_finishes_within_a_second",
    "core/tests/test_pages.py::test_healthz_returns_200_when_database_is_busy",
]
REFUSALS = {
    "redirect_to_login",
    "HttpResponseBadRequest",
    "HttpResponseForbidden",
    "HttpResponseNotAllowed",
    "HttpResponseNotFound",
}


def _call_name(call) -> str:
    func = call.func
    return func.id if isinstance(func, ast.Name) else getattr(func, "attr", "")


def _is_refusal(stmt) -> bool:
    if isinstance(stmt, ast.Raise):
        return True
    if isinstance(stmt, ast.Expr) and isinstance(stmt.value, ast.Call):
        func = stmt.value.func
        return (
            isinstance(func, ast.Attribute)
            and func.attr == "append"
            and isinstance(func.value, ast.Name)
            and func.value.id in COLLECTORS
        )
    if isinstance(stmt, ast.Return) and isinstance(stmt.value, ast.Call):
        call = stmt.value
        if _call_name(call) in REFUSALS:
            return True
        return any(
            kw.arg == "status"
            and isinstance(kw.value, ast.Constant)
            and isinstance(kw.value.value, int)
            and kw.value.value >= 400
            for kw in call.keywords
        )
    return False


def find_guards(relpath: str) -> list[dict]:
    source = (REPO / relpath).read_text()
    tree = ast.parse(source)
    guards = []

    def visit(node, scope):
        for child in ast.iter_child_nodes(node):
            inner = scope
            if isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
                inner = f"{scope}.{child.name}" if scope else child.name
            if isinstance(child, ast.If) and any(_is_refusal(s) for s in child.body):
                test = child.test
                guards.append(
                    {
                        "file": relpath,
                        "line": test.lineno,
                        "function": scope or "<module>",
                        "condition": " ".join(
                            ast.get_source_segment(source, test).split()
                        ),
                        "span": [
                            test.lineno,
                            test.col_offset,
                            test.end_lineno,
                            test.end_col_offset,
                        ],
                    }
                )
            visit(child, inner)

    visit(tree, "")
    return guards


def mutate(source: str, span) -> str:
    """Replace the condition with False. ast offsets are UTF-8 byte offsets."""
    raw = source.encode()
    starts = [0]
    for line in raw.splitlines(keepends=True):
        starts.append(starts[-1] + len(line))
    start = starts[span[0] - 1] + span[1]
    end = starts[span[2] - 1] + span[3]
    return (raw[:start] + b"False" + raw[end:]).decode()


def test_dir_for(relpath: str) -> str | None:
    tests = relpath.split("/")[0] + "/tests"
    return tests if (REPO / tests).is_dir() else None


def pytest(copy: Path, *paths: str) -> tuple[int, list[str], str]:
    env = dict(os.environ, PYTHONDONTWRITEBYTECODE="1")
    proc = subprocess.run(
        [
            str(PYTHON),
            "-m",
            "pytest",
            "-x",
            "-q",
            "-p",
            "no:cacheprovider",
            *(f"--deselect={test}" for test in TIMING_TESTS),
            *paths,
        ],
        cwd=copy,
        env=env,
        capture_output=True,
        text=True,
        timeout=900,
    )
    lines = proc.stdout.splitlines()
    failed = [
        ln.split(" - ")[0] for ln in lines if ln.startswith(("FAILED ", "ERROR "))
    ]
    summaries = [ln for ln in lines if re.search(r"\d+ (passed|failed)", ln)]
    tail = summaries[-1] if summaries else ""
    return proc.returncode, failed, tail


def make_copy(dest: Path) -> None:
    if dest.exists():
        shutil.rmtree(dest)
    dest.mkdir(parents=True)
    archive = subprocess.run(
        [GIT, "archive", "HEAD"], cwd=REPO, capture_output=True, check=True
    ).stdout
    subprocess.run(["tar", "-x", "-C", str(dest)], input=archive, check=True)
    # Built CSS is gitignored but the page-weight tests read it.
    css = REPO / "static" / "css" / "app.css"
    if css.exists():
        shutil.copy2(css, dest / "static" / "css" / "app.css")
    # Tests and test files of the working tree, so uncommitted tests count too.
    for tests in REPO.glob("*/tests"):
        shutil.copytree(tests, dest / tests.relative_to(REPO), dirs_exist_ok=True)


def run_one(copy: Path, guard: dict) -> dict:
    target = copy / guard["file"]
    original = target.read_text()
    target.write_text(mutate(original, guard["span"]))
    started = time.monotonic()
    try:
        tests = test_dir_for(guard["file"])
        code, failed, tail = pytest(copy, tests) if tests else (0, [], "")
        stage = "app"
        if code == 0:
            code, failed, tail = pytest(copy)
            stage = "full"
    finally:
        target.write_text(original)
    result = "caught" if code == 1 else "survived" if code == 0 else f"error({code})"
    return {
        **guard,
        "result": result,
        "stage": stage,
        "failed": failed[:1],
        "tail": tail,
        "seconds": round(time.monotonic() - started, 1),
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--list", action="store_true")
    parser.add_argument("--workers", type=int, default=4)
    parser.add_argument("--copies", type=Path, default=None)
    parser.add_argument("--out", type=Path, default=Path("mutants.jsonl"))
    parser.add_argument("--only", default="", help="只跑路径包含这个字符串的文件")
    parser.add_argument(
        "--resume",
        type=Path,
        action="append",
        default=[],
        help="跳过这些结果文件里已经跑过的守卫（可以给多次）。"
        "按文件、函数和条件匹配，不按行号：跑完之后代码可能挪了行",
    )
    args = parser.parse_args()

    guards = [g for path in targets() if args.only in path for g in find_guards(path)]
    done = set()
    for previous in args.resume:
        for line in previous.read_text().splitlines():
            row = json.loads(line)
            done.add((row["file"], row["function"], row["condition"]))
    if done:
        before = len(guards)
        guards = [
            g for g in guards if (g["file"], g["function"], g["condition"]) not in done
        ]
        skipped = before - len(guards)
        print(f"续跑：{before} 个守卫里 {skipped} 个已经跑过，剩 {len(guards)} 个")
    if args.list:
        for g in guards:
            print(f"{g['file']}:{g['line']}  {g['function']}  if {g['condition']}")
        print(f"共 {len(guards)} 个守卫")
        return

    root = args.copies or Path(os.environ.get("TMPDIR", "/tmp")) / "mutate-guards"
    copies = [root / f"w{i}" for i in range(args.workers)]
    for copy in copies:
        make_copy(copy)

    print("基线（并行负载下，未变异）：", flush=True)
    with ThreadPoolExecutor(args.workers) as pool:
        baselines = list(pool.map(lambda c: pytest(c), copies))
    for copy, (code, failed, tail) in zip(copies, baselines, strict=True):
        print(f"  {copy.name}: exit={code} {tail} {failed}", flush=True)
    if any(code != 0 for code, _, _ in baselines):
        sys.exit("基线不绿，变异结果没有意义。")

    free = list(copies)
    lock = threading.Lock()

    def work(guard):
        with lock:
            copy = free.pop()
        try:
            return run_one(copy, guard)
        finally:
            with lock:
                free.append(copy)

    done = 0
    with args.out.open("w") as out, ThreadPoolExecutor(args.workers) as pool:
        for result in pool.map(work, guards):
            done += 1
            out.write(json.dumps(result, ensure_ascii=False) + "\n")
            out.flush()
            mark = {"caught": "✓", "survived": "✗"}.get(result["result"], "?")
            print(
                f"[{done}/{len(guards)}] {mark} {result['file']}:{result['line']} "
                f"{result['function']}  if {result['condition'][:60]}",
                flush=True,
            )


if __name__ == "__main__":
    main()
