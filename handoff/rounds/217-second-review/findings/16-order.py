"""217 复核 16：测试之间通过 django_cache 表串味（顺序依赖）的复现。

transaction=True 的测试提交的缓存行不会被 flush 清掉（缓存表不是模型），
--reuse-db 下连下一次 pytest 都看得到。test_pages 的「数据库忙」测试写了一个
新鲜的 worker 心跳（有效期 240 秒），之后 240 秒内跑「worker 停了待办要提醒」
的测试就红。同一次运行里因为文件按字母排（test_admin_functions 在 test_pages
前面）碰不上；分片的工作树跨两次检查保留同一个 test.sqlite3，两次检查隔得近、
两条测试又分进同一片时就会碰上。

在 git archive 出来的临时副本里跑，不往测试机仓库的测试库里留东西。

    bash scripts/remote-check.sh run .venv/bin/python handoff/rounds/217-second-review/findings/16-order.py
"""

import importlib.util
import shutil
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[4]
spec = importlib.util.spec_from_file_location(
    "mg", ROOT / "handoff/rounds/210-full-review/mutate_guards.py"
)
mg = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mg)

BUSY = "core/tests/test_pages.py::test_healthz_returns_200_when_database_is_busy"
DOWN = "core/tests/test_admin_functions.py::test_the_owner_hears_when_the_worker_is_down"


def pytest(copy, *args):
    proc = subprocess.run(
        [str(ROOT / ".venv/bin/python"), "-m", "pytest", "-q", "-p", "no:cacheprovider", *args],
        cwd=copy,
        capture_output=True,
        text=True,
    )
    lines = (proc.stdout + proc.stderr).splitlines()
    keep = [ln for ln in lines if ln.startswith(("FAILED", "ERROR", "E  ")) or " passed" in ln or " failed" in ln]
    return proc.returncode, keep[-8:]


def main():
    copy = Path("/tmp/sjtu-ow-217-16/order")
    mg.make_copy(copy)
    try:
        print("1. 对照：只跑「worker 停了」那条", flush=True)
        print(*pytest(copy, "--create-db", DOWN), sep="\n", flush=True)
        print("2. 同一次 pytest：先「数据库忙」（transaction=True，写心跳），再「worker 停了」", flush=True)
        print(*pytest(copy, BUSY, DOWN), sep="\n", flush=True)
        print("3. 两次 pytest（--reuse-db，就像分片的工作树跨两次检查）：先跑「数据库忙」", flush=True)
        print(*pytest(copy, BUSY), sep="\n", flush=True)
        print("   再单独跑「worker 停了」", flush=True)
        print(*pytest(copy, DOWN), sep="\n", flush=True)
    finally:
        shutil.rmtree(copy, ignore_errors=True)


if __name__ == "__main__":
    main()
