"""Break each new rule of round 086 once and check a test goes red.

    uv run python handoff/rounds/086-v4-system-home/mutate.py

The baseline is run first: a red baseline makes every mutation look killed
(round 083).
"""

import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
TESTS = [
    "core/tests/test_design_system.py",
    "content/tests/test_home_sections.py",
]
CSS = "assets/css/input.css"
HOME = "content/templates/content/home_page.html"

MUTATIONS = [
    ("深色块漏写一个颜色", CSS, "    --color-fg-3: #8f97a3;\n", ""),
    ("深色的第三级文字对比度不够", CSS, "--color-fg-3: #8f97a3;", "--color-fg-3: #4a505b;"),
    ("浅色控件边框对比度不够", CSS, "--color-control: #767d88;", "--color-control: #9aa1ab;"),
    (
        "页头又磨砂",
        CSS,
        "    border-bottom: 1px solid var(--color-line);\n    background-color: var(--color-surface);\n  }\n\n  .c-masthead__bar {",
        "    border-bottom: 1px solid var(--color-line);\n    background-color: var(--color-surface);\n    backdrop-filter: blur(20px);\n  }\n\n  .c-masthead__bar {",
    ),
    (
        "又加渐变色块",
        CSS,
        "  .c-stats {\n    border-bottom: 1px solid var(--color-line);",
        "  .c-stats {\n    background-image: radial-gradient(var(--color-primary-soft), transparent);\n    border-bottom: 1px solid var(--color-line);",
    ),
    (
        "首页网格不用 minmax(0",
        CSS,
        "grid-template-columns: minmax(0, 7fr) minmax(0, 5fr);",
        "grid-template-columns: 7fr 5fr;",
    ),
    (
        "没上传首屏图时不放校徽",
        HOME,
        """      <img class="c-hero__emblem" src="{% static 'img/sjtu-emblem.svg' %}" alt="" width="560" height="560">\n""",
        "",
    ),
    (
        "QQ 按钮不用图上的白色描边",
        HOME,
        'class="c-btn c-btn--light" rel="noopener"',
        'class="c-btn c-btn--secondary" rel="noopener"',
    ),
    (
        "大图卡取最晚截止的赛事",
        "content/home.py",
        "first = min(tournaments, key=lambda item: item.registration_closes_at)",
        "first = max(tournaments, key=lambda item: item.registration_closes_at)",
    ),
    (
        "内战不按开始时间排",
        "content/home.py",
        "chosen = sorted(scrims, key=lambda item: item.starts_at)[:limit]",
        "chosen = list(scrims)[:limit]",
    ),
    (
        "累计内战把没打的也算上",
        "content/home.py",
        "return Scrim.objects.filter(status=ScrimStatus.FINISHED).count()",
        "return Scrim.objects.count()",
    ),
    (
        "改首屏图片不刷新首页",
        "core/signals.py",
        'HOMEPAGE_FIELDS = ("founded_on", "qq_group_url", "hero_image_id")',
        'HOMEPAGE_FIELDS = ("founded_on", "qq_group_url")',
    ),
    (
        "页脚不写游戏图片版权",
        "templates/base.html",
        " · 游戏图片版权归暴雪娱乐所有",
        "",
    ),
    (
        "内容又等脚本才出现",
        "static/js/state.js",
        '  var d = document;\n',
        '  var d = document;\n  d.documentElement.className += " js";\n',
    ),
]


def clear_pycache():
    for path in ROOT.rglob("__pycache__"):
        if ".venv" in path.parts:
            continue
        shutil.rmtree(path, ignore_errors=True)


def run_tests():
    return subprocess.run(
        [sys.executable, "-m", "pytest", "-q", "-x", *TESTS],
        cwd=ROOT,
        capture_output=True,
        text=True,
        encoding="utf-8",
    )


def main():
    baseline = run_tests()
    print("BASELINE", baseline.stdout.strip().splitlines()[-1])
    if baseline.returncode != 0:
        print("baseline is red; fix the tests first")
        return
    killed = 0
    for label, rel, old, new in MUTATIONS:
        path = ROOT / rel
        original = path.read_text(encoding="utf-8")
        if old not in original:
            print(f"MISSING  {label}")
            continue
        path.write_text(original.replace(old, new, 1), encoding="utf-8")
        try:
            result = run_tests()
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
