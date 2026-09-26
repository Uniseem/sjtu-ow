"""Break each new rule of round 081 once and check a test goes red.

    uv run python handoff/rounds/081-material3-system/mutate.py

The design-system tests read assets/css/input.css directly, so app.css is not
rebuilt. The chrome tests render templates through the test client.
"""

import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
TESTS = ["core/tests/test_design_system.py"]
CSS = "assets/css/input.css"

MUTATIONS = [
    ("第三级文字调得太浅（不到 4.5）", CSS,
     "--color-on-surface-3: #6b5a58;", "--color-on-surface-3: #9a8a88;"),
    ("控件边框用回装饰线的颜色（不到 3）", CSS,
     "--color-outline: #857371;", "--color-outline: #d8c2bf;"),
    ("图标片颜色太浅，白色图标看不清", CSS,
     "--color-chip-sky: #3d6a8a;", "--color-chip-sky: #8fb1cf;"),
    ("提示条的字和底对比不够", CSS,
     "--color-inverse-on-surface: #fbeeec;", "--color-inverse-on-surface: #6b5a58;"),
    ("令牌以外写 rgb() 半透明色", CSS,
     "background-color: color-mix(in oklab, var(--color-on-surface) 5%, transparent);",
     "background-color: rgb(35 25 24 / 0.05);"),
    ("色调区块把文字翻成浅色", CSS,
     "  --tone-bg: var(--color-surface-mid);\n",
     "  --tone-bg: var(--color-surface-mid);\n  --tone-fg: var(--color-surface);\n"),
    ("页头换回不透明的实底", CSS,
     "    background-color: var(--glass-bg);\n    -webkit-backdrop-filter: var(--glass-filter);",
     "    background-color: var(--color-surface-lowest);\n    -webkit-backdrop-filter: var(--glass-filter);"),
    ("胶囊不是圆角", CSS,
     "    height: 3.25rem;\n    border: 1px solid var(--glass-line);\n    border-radius: var(--radius-full);",
     "    height: 3.25rem;\n    border: 1px solid var(--glass-line);\n    border-radius: 0;"),
    ("收起时不移出屏幕", CSS,
     "transform: translate3d(0, calc(-100% - 1.5rem), 0);", "transform: none;"),
    ("滚动出现不看 .js 就隐藏内容", CSS,
     ".js [data-reveal] > * {\n  opacity: 0;", "[data-reveal] > * {\n  opacity: 0;"),
    ("js 类放到提前返回之后", "static/js/state.js",
     '  d.documentElement.className += " js";\n', ""),
    ("motion.js 没来时不撤掉 .js（内容一直藏着）", "static/js/state.js",
     'root.className = root.className.replace(" js", "");', "void 0;"),
    ("收起时不顾键盘焦点", "static/js/motion.js",
     "if (hidden && bar.contains(d.activeElement)) {", "if (false) {"),
    ("页头没有接上 motion.js", "templates/base.html",
     '<header class="c-masthead" data-masthead>', '<header class="c-masthead">'),
    ("抽屉导航又带编号", "templates/components/main_nav.html",
     '{% endif %}>首页</a>', '{% endif %}><span>01</span>首页</a>'),
    ("校徽文件回到整页 A4 画布", "static/img/sjtu-emblem.svg",
     'viewBox="167.84 146.61 283.5 283.51"', 'viewBox="0 0 595.276 841.89"'),
    ("第三方声明漏登记校徽", "THIRD_PARTY_NOTICES.md",
     "（`static/img/sjtu-emblem.svg`）", ""),
    ("错误页的主色和站点不一致", "static/css/error.css",
     "--color-primary: #b2141a;", "--color-primary: #b2141b;"),
    ("样张页色块还写旧值", "core/styleguide.py",
     '("第三级文字", "on-surface-3", "bg-on-surface-3", "#6B5A58")',
     '("第三级文字", "on-surface-3", "bg-on-surface-3", "#726A68")'),
]


def clear_pycache():
    for path in ROOT.rglob("__pycache__"):
        if ".venv" in path.parts:
            continue
        shutil.rmtree(path, ignore_errors=True)


def main():
    killed = 0
    for label, rel, old, new in MUTATIONS:
        path = ROOT / rel
        original = path.read_text(encoding="utf-8")
        if old not in original:
            print(f"MISSING  {label}")
            continue
        path.write_text(original.replace(old, new, 1), encoding="utf-8")
        try:
            result = subprocess.run(
                [sys.executable, "-m", "pytest", "-q", "-x", *TESTS],
                cwd=ROOT,
                capture_output=True,
                text=True,
                encoding="utf-8",
            )
        finally:
            path.write_text(original, encoding="utf-8")
            clear_pycache()
        summary = result.stdout.strip().splitlines()[-1] if result.stdout else ""
        if result.returncode != 0:
            killed += 1
            print(f"KILLED   {label}  | {summary}")
        else:
            print(f"SURVIVED {label}  | {summary}")
    print(f"{killed}/{len(MUTATIONS)} killed")


if __name__ == "__main__":
    main()
