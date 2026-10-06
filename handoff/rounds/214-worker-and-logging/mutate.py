"""Round 214 mutation check: every guard this round adds must turn red when
broken. Baseline first (083's lesson): if the baseline is red, stop.

Run: uv run python handoff/rounds/214-worker-and-logging/mutate.py
"""

import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]

# (name, file, old, new, tests that must go red)
MUTATIONS = [
    (
        "C1: SMTP 不带超时",
        "core/mail.py",
        "        timeout=SMTP_TIMEOUT_SECONDS,\n",
        "",
        ["core/tests/test_mail.py::test_smtp_backend_gives_up_after_20_seconds"],
    ),
    (
        "C2: 复位不写回 READY",
        "core/worker.py",
        "        result.status = TaskResultStatus.READY\n",
        "        result.status = result.status\n",
        [
            "core/tests/test_worker_recovery.py::test_orphaned_running_tasks_go_back_to_ready",
        ],
    ),
    (
        "C2: run_worker 启动不复位",
        "core/management/commands/run_worker.py",
        "        reset_orphaned_running_tasks()\n",
        "",
        ["core/tests/test_worker_recovery.py::test_run_worker_resets_before_taking_work"],
    ),
    (
        "C3: 请求编号又采用客户端的",
        "core/middleware.py",
        "        request_id = get_random_string(12)\n",
        '        request_id = request.headers.get("X-Request-ID") or get_random_string(12)\n',
        [
            "core/tests/test_error_logging.py::test_the_request_id_ignores_the_client_header",
        ],
    ),
    (
        "C3: 500 不记日志行",
        "core/views.py",
        """    logger.error(
        "500 request_id=%s path=%s", request_id or "-", request.path, exc_info=False
    )
""",
        "",
        [
            "core/tests/test_error_logging.py::test_the_500_line_ties_the_request_id_to_the_path",
        ],
    ),
    (
        "C3: 生产 django.request 不落日志",
        "sjtu_ow/settings/prod.py",
        """        "django.request": {
            "handlers": ["console"],
            "level": "ERROR",
            "propagate": False,
        },
""",
        "",
        ["core/tests/test_security_guards.py::test_prod_logging_sends_request_errors_to_stdout"],
    ),
]

BASELINE = sorted({test for _m in MUTATIONS for test in _m[4]})


def run(tests):
    result = subprocess.run(
        ["uv", "run", "pytest", "-q", *tests],
        cwd=ROOT,
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        tail = "\n".join((result.stdout + result.stderr).splitlines()[-12:])
        print(f"    ---- 输出尾巴 ----\n{tail}")
    return result.returncode


def main():
    print("基线：", flush=True)
    if run(BASELINE) != 0:
        print("基线就是红的，停下（083 的教训）。")
        return 1
    print("基线全绿，开始变异。\n", flush=True)
    bad = 0
    for name, filename, old, new, tests in MUTATIONS:
        path = ROOT / filename
        original = path.read_text(encoding="utf-8")
        if old not in original:
            print(f"!! {name}：找不到要改坏的代码（{filename}），跳过")
            bad += 1
            continue
        backup = path.with_suffix(path.suffix + ".bak214")
        shutil.copy2(path, backup)
        try:
            path.write_text(original.replace(old, new, 1), encoding="utf-8")
            code = run(tests)
            if code == 0:
                print(f"!! {name}：改坏后测试仍然全绿 —— 没抓到")
                bad += 1
            else:
                print(f"ok {name}：改坏后红了（{len(tests)} 条）")
        finally:
            shutil.move(backup, path)
            # 027 的坑：mtime/size 没变时清掉缓存再跑
            for cache in path.parent.glob(f"__pycache__/{path.stem}.*"):
                cache.unlink()
    print()
    if run(BASELINE) != 0:
        print("!! 改回之后基线红了，有文件没恢复好")
        return 1
    print("改回后基线全绿。")
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
