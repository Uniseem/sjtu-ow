"""236：把内容安全策略和脚本体积上限改坏，确认测试会红，再改回来。"""

import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
SERVER = ROOT / "web" / "apps" / "site" / "server.ts"
BUDGET = ROOT / "web" / "apps" / "site" / "budget.mjs"


def once(text, old, new):
    count = text.count(old)
    if count != 1:
        sys.exit(f"要改的原文出现了 {count} 次，不是 1 次：{old!r}")
    return text.replace(old, new, 1)


def run():
    return subprocess.run(["pnpm", "test"], cwd=ROOT / "web").returncode


def main():
    server = SERVER.read_text(encoding="utf-8")
    budget = BUDGET.read_text(encoding="utf-8")
    if run() != 0:
        sys.exit("基线不是绿的，先修测试")
    cases = [
        (
            "A 策略少了 frame-src",
            SERVER,
            server,
            "frame-src 'self' https://player.bilibili.com; ",
            "",
        ),
        (
            "B 脚本上限改成 1 KB",
            BUDGET,
            budget,
            "const JS_GZIP_MAX = 120 * 1024\n",
            "const JS_GZIP_MAX = 1 * 1024\n",
        ),
    ]
    try:
        for name, path, original, old, new in cases:
            path.write_text(once(original, old, new), encoding="utf-8")
            code = run()
            path.write_text(original, encoding="utf-8")
            if code == 0:
                sys.exit(f"没抓到：{name}")
            print(f"抓到 {name}（退出码 {code}）")
    finally:
        SERVER.write_text(server, encoding="utf-8")
        BUDGET.write_text(budget, encoding="utf-8")
    if run() != 0:
        sys.exit("改回来之后不是绿的")
    print("两处都抓到，已改回")


if __name__ == "__main__":
    main()
