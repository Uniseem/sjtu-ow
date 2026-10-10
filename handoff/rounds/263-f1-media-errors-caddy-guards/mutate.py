"""263：把这一轮的守卫逐个拆掉，确认对应的测试会红，再改回来（硬规则 7）。

在测试机上跑：bash scripts/remote-check.sh run python3 handoff/rounds/263-f1-media-errors-caddy-guards/mutate.py
先跑基线（三组都要绿），再逐处变异；要改的原文都核过只出现一次。
"""

import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]

COMMANDS = {
    "caddy": (["bash", "e2e/caddy/smoke.sh"], ROOT),
    "go": (["go", "test", "-count=1", "./internal/platform/media/", "./internal/content/"], ROOT / "server"),
    "site": (["pnpm", "exec", "vitest", "run"], ROOT / "web" / "apps" / "site"),
}

CADDY = "deploy/Caddyfile.new"
CASES = [
    (
        "转给 Go 的访客 IP 换回 {remote_host}",
        CADDY,
        "\treverse_proxy {$API_UPSTREAM:server:8080} {\n\t\theader_up X-Real-IP {client_ip}\n",
        "\treverse_proxy {$API_UPSTREAM:server:8080} {\n\t\theader_up X-Real-IP {remote_host}\n",
        "caddy",
    ),
    (
        "转给 SSR 的访客 IP 换回 {remote_host}",
        CADDY,
        "\treverse_proxy {$SSR_UPSTREAM:web:5173} {\n\t\theader_up X-Real-IP {client_ip}\n",
        "\treverse_proxy {$SSR_UPSTREAM:web:5173} {\n\t\theader_up X-Real-IP {remote_host}\n",
        "caddy",
    ),
    (
        "缺的缩略图不回源 Go",
        CADDY,
        "\t\t\thandle {\n\t\t\t\timport to_api\n\t\t\t}\n\t\t}\n\n\t\t# 旧缩略图",
        "\t\t}\n\n\t\t# 旧缩略图",
        "caddy",
    ),
    (
        "一键退订的 POST 不去 Go",
        CADDY,
        "\t\thandle @unsubscribe_post {\n\t\t\timport to_api\n\t\t}\n",
        "",
        "caddy",
    ),
    (
        "接口没有 1 MB 上限",
        CADDY,
        "\t\trequest_body @api_body {\n\t\t\tmax_size 1MB\n\t\t}\n",
        "",
        "caddy",
    ),
    (
        "CSP 不推迟设置（上游的 CSP 留着）",
        CADDY,
        "\t\t>Content-Security-Policy \"default-src 'self'; script-src 'self';",
        "\t\t+Content-Security-Policy \"default-src 'self'; script-src 'self';",
        "caddy",
    ),
    (
        "错误页不链 error.css",
        "web/apps/site/src/error-page.ts",
        '    <link rel="stylesheet" href="${ERROR_CSS}">\n',
        "",
        "site",
    ),
    (
        "加载器的错误全当 503",
        "web/apps/site/src/entry-server.ts",
        "  return 500\n}\n",
        "  return 503\n}\n",
        "site",
    ),
    (
        "渲染抛错不再给 500 页",
        "web/apps/site/server.ts",
        "    out = errorResponse(500, req)\n",
        "    throw err\n",
        "site",
    ),
    (
        "服务端渲染在生产里吞掉组件的错误",
        "web/apps/site/src/main.ts",
        "  if (ssr) app.config.throwUnhandledErrorInProduction = true\n",
        "",
        "site",
    ),
    (
        "站点地图的文章地址没有结尾斜杠",
        "server/internal/content/sitemap.go",
        'func(k string) string { return "/news/" + k + "/" }',
        'func(k string) string { return "/news/" + k }',
        "go",
    ),
    (
        "站点地图收了解散的战队",
        "server/internal/content/sitemap.go",
        "FROM teams WHERE disbanded_at IS NULL ORDER BY id",
        "FROM teams ORDER BY id",
        "go",
    ),
    (
        "出图不查规格白名单",
        "server/internal/platform/media/api.go",
        "\tif !okID || !okExt || !okSpec {\n",
        "\tif !okID || !okExt {\n\t\t_ = okSpec\n",
        "go",
    ),
    (
        "守卫的色板正则失效",
        "web/apps/site/src/guards.test.ts",
        "slate|gray|zinc|neutral|stone|red",
        "slate|gray|zinc|neutral|red",
        "site",
    ),
    (
        "待重写列表多了一个干净的文件",
        "web/apps/site/src/guards.test.ts",
        '  "pages/ArticleDetail.vue",\n',
        '  "pages/ArticleDetail.vue",\n  "pages/Page.vue",\n',
        "site",
    ),
]


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
        try:
            path.write_text(once(original, old, new), encoding="utf-8")
            code = run(kind)
        finally:
            path.write_text(original, encoding="utf-8")
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
