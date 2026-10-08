"""238：拿掉样张的 main，以及样张色块的扫描，确认测试会红，再改回来。"""

import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
PAGE = ROOT / "web" / "apps" / "site" / "src" / "pages" / "Styleguide.vue"
CSS = ROOT / "web" / "packages" / "styles" / "input.css"


def once(text, old, new):
    count = text.count(old)
    if count != 1:
        sys.exit(f"要改的原文出现了 {count} 次，不是 1 次：{old!r}")
    return text.replace(old, new, 1)


def run():
    return subprocess.run(["pnpm", "test"], cwd=ROOT / "web").returncode


def main():
    page = PAGE.read_text(encoding="utf-8")
    css = CSS.read_text(encoding="utf-8")
    if run() != 0:
        sys.exit("基线不是绿的，先修测试")
    cases = [
        (
            "A 样张去掉 id=main",
            PAGE,
            page,
            '  <main id="main" class="flex-1">\n  <header class="c-pagehead">\n',
            '  <main class="flex-1">\n  <header class="c-pagehead">\n',
        ),
        (
            "B 不再扫描 specimen.ts",
            CSS,
            css,
            '@source "../../apps/site/src/specimen.ts";\n',
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
        PAGE.write_text(page, encoding="utf-8")
        CSS.write_text(css, encoding="utf-8")
    if run() != 0:
        sys.exit("改回来之后不是绿的")
    print("两处都抓到，已改回")


if __name__ == "__main__":
    main()
