"""235：把样张的门、按钮和名额格改坏，确认测试会红，再改回来。"""

import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
SPECIMEN = ROOT / "web" / "apps" / "site" / "src" / "specimen.ts"
PAGE = ROOT / "web" / "apps" / "site" / "src" / "pages" / "Styleguide.vue"


def once(text, old, new):
    count = text.count(old)
    if count != 1:
        sys.exit(f"要改的原文出现了 {count} 次，不是 1 次：{old!r}")
    return text.replace(old, new, 1)


def run():
    return subprocess.run(["pnpm", "test"], cwd=ROOT / "web").returncode


def main():
    specimen = SPECIMEN.read_text(encoding="utf-8")
    page = PAGE.read_text(encoding="utf-8")
    if run() != 0:
        sys.exit("基线不是绿的，先修测试")
    cases = [
        (
            "A 样张对访客开放",
            SPECIMEN,
            specimen,
            'return path.startsWith("/_styleguide/") && !admin\n',
            "return false\n",
        ),
        (
            "B 拿掉为战队报名",
            PAGE,
            page,
            "为战队报名",
            "为战队看看",
        ),
        (
            "C 名额格不再涂色",
            SPECIMEN,
            specimen,
            "const filled = Math.min(cells, Math.round((got * cells) / need))\n",
            "const filled = 0\n",
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
        SPECIMEN.write_text(specimen, encoding="utf-8")
        PAGE.write_text(page, encoding="utf-8")
    if run() != 0:
        sys.exit("改回来之后不是绿的")
    print("三处都抓到，已改回")


if __name__ == "__main__":
    main()
