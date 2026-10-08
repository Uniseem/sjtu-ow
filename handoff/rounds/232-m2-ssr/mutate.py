"""232：把 SSR 的三条守卫改坏，确认测试会红，再改回来。"""

import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
SERVER = ROOT / "web" / "apps" / "site" / "server.ts"


def once(text, old, new):
    count = text.count(old)
    if count != 1:
        sys.exit(f"要改的原文出现了 {count} 次，不是 1 次：{old!r}")
    return text.replace(old, new, 1)


def run():
    return subprocess.run(["pnpm", "--filter", "@sjtu-ow/site", "test"], cwd=ROOT / "web").returncode


def main():
    original = SERVER.read_text(encoding="utf-8")
    if run() != 0:
        sys.exit("基线不是绿的，先修测试")
    cases = {
        "A 放行 POST": (
            'if (method !== "GET" && method !== "HEAD") {',
            'if (method !== "GET" && method !== "POST") {',
        ),
        "B 不转义小于号": (
            '    .replaceAll("<", "\\\\u003c")\n',
            "\n",
        ),
        "C 登录用户也能被缓存": (
            'rendered.loggedIn ? "private, no-store" : "no-cache"',
            'rendered.loggedIn ? "no-cache" : "no-cache"',
        ),
    }
    try:
        for name, (old, new) in cases.items():
            SERVER.write_text(once(original, old, new), encoding="utf-8")
            code = run()
            SERVER.write_text(original, encoding="utf-8")
            if code == 0:
                sys.exit(f"没抓到：{name}")
            print(f"抓到 {name}（退出码 {code}）")
    finally:
        SERVER.write_text(original, encoding="utf-8")
    if run() != 0:
        sys.exit("改回来之后不是绿的")
    print("三处都抓到，已改回")


if __name__ == "__main__":
    main()
