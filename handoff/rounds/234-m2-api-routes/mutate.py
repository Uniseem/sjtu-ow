"""234：把接口封装和资讯路由改坏，确认测试会红，再改回来。"""

import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
CLIENT = ROOT / "web" / "packages" / "api" / "src" / "client.ts"
ROUTES = ROOT / "web" / "apps" / "site" / "src" / "routes.ts"


def once(text, old, new):
    count = text.count(old)
    if count != 1:
        sys.exit(f"要改的原文出现了 {count} 次，不是 1 次：{old!r}")
    return text.replace(old, new, 1)


def run():
    return subprocess.run(["pnpm", "test"], cwd=ROOT / "web").returncode


def main():
    client = CLIENT.read_text(encoding="utf-8")
    routes = ROUTES.read_text(encoding="utf-8")
    if run() != 0:
        sys.exit("基线不是绿的，先修测试")
    cases = [
        (
            "A 401 不再跳登录",
            CLIENT,
            client,
            'if (response.status === 401) {\n      assign("/accounts/login/?next=" + encodeURIComponent(locate()))\n      throw new ApiError(401, "unauthorized", "登录已失效")\n    }\n',
            "",
        ),
        (
            "B 写请求不带幂等键",
            CLIENT,
            client,
            'if (WRITE.has(method)) headers.set("Idempotency-Key", options.key ?? newKey())\n',
            "",
        ),
        (
            "C 待发信跳错地址",
            CLIENT,
            client,
            'const base = here.startsWith("/admin/") ? "/admin/letters/" : "/letters/"\n',
            'const base = here.startsWith("/admin/") ? "/admin/mail/" : "/mail/"\n',
        ),
        (
            "D 资讯页被拿掉",
            ROUTES,
            routes,
            '  page("/news/", "资讯"),\n',
            "",
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
        CLIENT.write_text(client, encoding="utf-8")
        ROUTES.write_text(routes, encoding="utf-8")
    if run() != 0:
        sys.exit("改回来之后不是绿的")
    print("四处都抓到，已改回")


if __name__ == "__main__":
    main()
