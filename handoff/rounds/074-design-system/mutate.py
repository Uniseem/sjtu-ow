"""Break each new rule of round 074 once and check a test goes red.

    uv run python handoff/rounds/074-design-system/mutate.py

Every mutation is reverted (and __pycache__ cleared, AGENTS.md) before the
next one runs.
"""

import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
TESTS = "core/tests/test_design_system.py"

MUTATIONS = [
    (
        "--font-figure 不跟随字库字体",
        "core/fonts/css.py",
        'variables.append(f"  --font-figure: {_family_value(rule)};")',
        "pass",
    ),
    (
        "按钮区域的规则不管 c-btn",
        "core/fonts/css.py",
        '"button": ".font-button, .c-btn",',
        '"button": ".font-button",',
    ),
    (
        "样张页对所有人开放",
        "core/styleguide.py",
        "if not (user.is_authenticated and user.has_perm(ADMIN_PERMISSION)):",
        "if False:",
    ),
    (
        "样张页只给超级管理员",
        "core/styleguide.py",
        "if not (user.is_authenticated and user.has_perm(ADMIN_PERMISSION)):",
        "if not user.is_superuser:",
    ),
    (
        "robots 不禁止样张页",
        "content/views.py",
        '"Disallow: /_styleguide/",',
        "",
    ),
    (
        "样张页的地址能被页面占用",
        "content/models.py",
        '"_styleguide",',
        "",
    ),
    (
        "导航不标当前栏目",
        "templates/components/main_nav.html",
        '<a href="/news/"{% if "/news/" in p %} aria-current="page"{% endif %}>',
        '<a href="/news/">',
    ),
    (
        "手机菜单改成靠脚本的 div",
        "templates/base.html",
        '<details class="c-drawer lg:hidden">',
        '<div class="c-drawer lg:hidden">',
    ),
    (
        "抽屉导航不编号",
        "templates/base.html",
        '{% include "components/main_nav.html" with numbered=True %}',
        '{% include "components/main_nav.html" %}',
    ),
    (
        "去掉网站图标",
        "templates/base.html",
        "<link rel=\"icon\" href=\"{% static 'img/favicon.svg' %}\" type=\"image/svg+xml\">",
        "",
    ),
    (
        # The footer says it twice (statement and base line); remove both.
        "页脚不写非官方",
        "templates/base.html",
        "不是上海交通大学官方网站",
        "",
        "all",
    ),
    (
        "账号菜单不用 details",
        "templates/components/account_area.html",
        '<details class="c-menu">',
        '<div class="c-menu">',
    ),
    (
        "error.css 的红色和令牌不一致",
        "static/css/error.css",
        "--color-red: #b2141a;",
        "--color-red: #c8161d;",
    ),
    (
        "留着 Tailwind 自带的颜色",
        "assets/css/input.css",
        "  --color-*: initial;\n",
        "",
    ),
    (
        "超出上限不标出来",
        "core/templatetags/ow.py",
        'cells += ["over"] * max(taken - capacity, 0)',
        "pass",
    ),
    (
        "超过 24 格仍然画方块",
        "core/templatetags/ow.py",
        "if max(taken, capacity) > SLOT_CELL_LIMIT:",
        "if False:",
    ),
    (
        "时间不换算成上海时间",
        "core/templatetags/ow.py",
        "            return timezone.localtime(value)\n",
        "            return value\n",
    ),
    (
        "星期从周日开始数",
        "core/templatetags/ow.py",
        'WEEKDAYS = "一二三四五六日"',
        'WEEKDAYS = "日一二三四五六"',
    ),
    (
        "段位小段不用数字字体",
        "templates/components/rank_badge.html",
        '<span class="c-rank__div">{{ parts.1 }}</span>',
        "{{ parts.1 }}",
    ),
]


def clear_pycache():
    for path in ROOT.rglob("__pycache__"):
        if ".venv" in path.parts:
            continue
        shutil.rmtree(path, ignore_errors=True)


def main():
    killed = 0
    for label, rel, old, new, *mode in MUTATIONS:
        path = ROOT / rel
        original = path.read_text(encoding="utf-8")
        if old not in original:
            print(f"MISSING  {label}")
            continue
        count = -1 if mode == ["all"] else 1
        path.write_text(original.replace(old, new, count), encoding="utf-8")
        try:
            result = subprocess.run(
                [sys.executable, "-m", "pytest", "-q", "-x", TESTS],
                cwd=ROOT,
                capture_output=True,
                text=True,
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
