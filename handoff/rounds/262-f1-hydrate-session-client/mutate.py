"""262：把这一轮的每道守卫拆掉，确认对应的测试会红，再改回来（硬规则 7）。

在测试机上跑：bash scripts/remote-check.sh run python3 handoff/rounds/262-f1-hydrate-session-client/mutate.py
先跑基线（三组命令都要绿），再逐处变异。要改的原文都核过只出现一次（216 的坑）。
"""

import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
SITE = ROOT / "web" / "apps" / "site"

GO_API = ["go", "test", "./internal/platform/api/", "./internal/platform/apigen/"]
VITEST = ["pnpm", "exec", "vitest", "run"]
BROWSER = ["bash", "-c", "pnpm --filter @sjtu-ow/site build >/dev/null 2>&1 && cd apps/site && node browser-check.mjs /usr/bin/chromium"]

COMMANDS = {
    "go": (GO_API, ROOT / "server"),
    "site": (VITEST, SITE),
    "api": (VITEST, ROOT / "web"),
    "browser": (BROWSER, ROOT / "web"),
}

CASES = [
    (
        "T1 注册表不再把 nil 切片换成空的",
        "server/internal/platform/api/registry.go",
        "body, err := json.Marshal(nonNil(out))",
        "body, err := json.Marshal(out)",
        "go",
    ),
    (
        "T2 apigen 的 []*T 不加括号",
        "server/internal/platform/apigen/apigen.go",
        '\t\t\tif strings.Contains(elem, " | ") {\n\t\t\t\telem = "(" + elem + ")"\n\t\t\t}\n',
        "",
        "go",
    ),
    (
        "T2 apigen 不摊平匿名嵌入",
        "server/internal/platform/apigen/apigen.go",
        "if name == \"\" && f.Anonymous && deref(f.Type).Kind() == reflect.Struct && !isTime(deref(f.Type)) {",
        "if false {",
        "go",
    ),
    (
        "T3 查询串不跳过空值",
        "web/packages/api/src/client.ts",
        '    if (value === undefined || value === null || value === "") continue\n',
        "",
        "api",
    ),
    (
        "T3 连不上不变成 ApiError(0)",
        "web/packages/api/src/client.ts",
        '      throw new ApiError(0, timedOut ? "timeout" : "network", timedOut ? "网站响应太慢" : "网络连不上")\n',
        "      throw err\n",
        "api",
    ),
    (
        "T3 unauthorized: throw 照样跳转",
        "web/packages/api/src/client.ts",
        '      if (options.unauthorized !== "throw") {\n        assign(',
        "      {\n        assign(",
        "api",
    ),
    (
        "T4 客户端换回 createApp（清空重画）",
        "web/apps/site/src/main.ts",
        "  const app = createSSRApp(App)\n",
        "  const app = (ssr ? createSSRApp : createCSRApp)(App)\n",
        "browser",
    ),
    (
        "T5 要登录的页不再先送访客去登录",
        "web/apps/site/src/entry-server.ts",
        '  if (route.meta.auth === "member" && viewer.user === null) return { kind: "login", next }\n',
        "",
        "site",
    ),
    (
        "T5 429 不再画成 429",
        "web/apps/site/src/entry-server.ts",
        "    if (status === 403 || status === 404 || status === 429) return page(status, viewer, head)\n",
        "    if (status === 403 || status === 404) return page(status, viewer, head)\n",
        "site",
    ),
    (
        "T5 会话只留昵称和 admin",
        "web/apps/site/src/entry-server.ts",
        "    return { user }\n",
        "    return { user: { nickname: user.nickname, admin: user.admin } as typeof user }\n",
        "site",
    ),
    (
        "T5 加载器拿不到查询参数",
        "web/apps/site/src/entry-server.ts",
        "    query: flat(route.query),\n",
        "    query: {},\n",
        "site",
    ),
]

# T4 needs createApp imported under another name for the mutant to compile.
EXTRA = {
    "T4 客户端换回 createApp（清空重画）": (
        "web/apps/site/src/main.ts",
        'import { createSSRApp } from "vue"\n',
        'import { createApp as createCSRApp, createSSRApp } from "vue"\n',
    ),
}


def run(kind):
    cmd, cwd = COMMANDS[kind]
    return subprocess.run(cmd, cwd=cwd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL).returncode


def once(text, old, new):
    count = text.count(old)
    if count != 1:
        sys.exit(f"要改的原文出现了 {count} 次，不是 1 次：{old!r}")
    return text.replace(old, new, 1)


def main():
    for kind in COMMANDS:
        if run(kind) != 0:
            sys.exit(f"基线不是绿的（{kind}），先修测试")
    print("基线全绿")
    caught = 0
    for name, rel, old, new, kind in CASES:
        path = ROOT / rel
        original = path.read_text(encoding="utf-8")
        extra = EXTRA.get(name)
        extra_original = None
        try:
            text = once(original, old, new)
            if extra and extra[0] == rel:
                text = once(text, extra[1], extra[2])
            elif extra:
                extra_original = (ROOT / extra[0]).read_text(encoding="utf-8")
                (ROOT / extra[0]).write_text(once(extra_original, extra[1], extra[2]), encoding="utf-8")
            path.write_text(text, encoding="utf-8")
            code = run(kind)
        finally:
            path.write_text(original, encoding="utf-8")
            if extra_original is not None:
                (ROOT / extra[0]).write_text(extra_original, encoding="utf-8")
        if code == 0:
            sys.exit(f"没抓到：{name}")
        caught += 1
        print(f"抓到 {name}（{kind} 退出码 {code}）")
    for kind in COMMANDS:
        if run(kind) != 0:
            sys.exit(f"改回来之后不是绿的（{kind}）")
    print(f"{caught} 处全抓到，已改回，基线仍全绿")


if __name__ == "__main__":
    main()
