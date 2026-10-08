"""237：把占位图的目录限制、样式地址、缓存和构建后的查找改坏，确认测试会红，再改回来。"""

import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
SERVER = ROOT / "web" / "apps" / "site" / "server.ts"
CSS = ROOT / "web" / "packages" / "styles" / "input.css"


def once(text, old, new):
    count = text.count(old)
    if count != 1:
        sys.exit(f"要改的原文出现了 {count} 次，不是 1 次：{old!r}")
    return text.replace(old, new, 1)


def run():
    return subprocess.run(["pnpm", "test"], cwd=ROOT / "web").returncode


def main():
    server = SERVER.read_text(encoding="utf-8")
    css = CSS.read_text(encoding="utf-8")
    if run() != 0:
        sys.exit("基线不是绿的，先修测试")
    cases = [
        (
            "A 目录限制拿掉",
            SERVER,
            server,
            "if (file !== base && !file.startsWith(base + sep)) return null\n",
            "",
        ),
        (
            "B 山脊图改回相对地址",
            CSS,
            css,
            'url("/static/img/placeholders/ridge.svg")',
            'url("../img/placeholders/ridge.svg")',
        ),
        (
            "C 缓存改成 max-age=0",
            SERVER,
            server,
            'export const STATIC_IMG_CACHE = "public, max-age=86400"\n',
            'export const STATIC_IMG_CACHE = "public, max-age=0"\n',
        ),
        (
            "D 构建产物找不到图",
            SERVER,
            server,
            'const starts = [fileURLToPath(new URL(".", import.meta.url)), process.cwd()]\n'
            '  const rels = ["../../../static/img", "../../../../static/img", "../../../../../static/img"]\n',
            'const starts = [fileURLToPath(new URL(".", import.meta.url))]\n'
            '  const rels = ["../../../static/img", "../../../../static/img"]\n',
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
        CSS.write_text(css, encoding="utf-8")
    if run() != 0:
        sys.exit("改回来之后不是绿的")
    print("四处都抓到，已改回")


if __name__ == "__main__":
    main()
