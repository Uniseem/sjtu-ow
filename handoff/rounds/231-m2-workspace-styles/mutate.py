"""231：把样式守卫改坏，确认 Vitest 会红，再改回来。"""

import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
CSS = ROOT / "web" / "packages" / "styles" / "input.css"


def once(text, old, new):
    count = text.count(old)
    if count != 1:
        sys.exit(f"要改的原文出现了 {count} 次，不是 1 次：{old!r}")
    return text.replace(old, new, 1)


def run():
    return subprocess.run(["pnpm", "test"], cwd=ROOT / "web").returncode


def main():
    original = CSS.read_text(encoding="utf-8")
    if run() != 0:
        sys.exit("基线不是绿的，先修测试")
    cases = {
        "A 色板重置被拿掉": (
            "  --color-*: initial;\n",
            "",
        ),
        "B prefers-color-scheme 出现两次": (
            "@custom-variant dark {\n  @media (prefers-color-scheme: dark) {",
            "@custom-variant dark {\n  /* prefers-color-scheme */\n  @media (prefers-color-scheme: dark) {",
        ),
        "C 深色块漏了 toast": (
            "    --color-toast: #e8eaee;\n    --color-on-toast: #1d2531;",
            "    --color-on-toast: #1d2531;",
        ),
    }
    try:
        for name, (old, new) in cases.items():
            CSS.write_text(once(original, old, new), encoding="utf-8")
            code = run()
            CSS.write_text(original, encoding="utf-8")
            if code == 0:
                sys.exit(f"没抓到：{name}")
            print(f"抓到 {name}（退出码 {code}）")
    finally:
        CSS.write_text(original, encoding="utf-8")
    if run() != 0:
        sys.exit("改回来之后不是绿的")
    print("三处都抓到，已改回")


if __name__ == "__main__":
    main()
