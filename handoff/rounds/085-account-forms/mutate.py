"""Break each new rule of round 085 once and check a test goes red.

    uv run python handoff/rounds/085-account-forms/mutate.py

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
    "comments/tests/test_comment_extras.py::test_the_static_page_shows_counts_placeholders_and_sort_links",
]
NAV = "templates/me/_nav.html"
ME = "templates/me/base.html"
WHY = "templates/account/_why.html"

MUTATIONS = [
    ("菜单用回编号", NAV,
     '{% include "components/icon.html" with name=icon class="size-5 c-sidenav__icon" %}',
     '<span class="c-sidenav__index">{{ forloop.counter|stringformat:"02d" }}</span>'),
    ("菜单两项共用一个图标", "accounts/views.py",
     '("me_scrims", "我的内战", True, "calendar")', '("me_scrims", "我的内战", True, "trophy")'),
    ("个人中心页头又带眉标", ME,
     "          <h1>{% block me_heading %}",
     '          <p class="c-eyebrow">ACCOUNT</p>\n          <h1>{% block me_heading %}'),
    ("个人中心页头没有头像", ME,
     '<span class="c-avatar c-avatar--sm" aria-hidden="true">{{ request.user.nickname|initial }}</span>', ""),
    ("登录不在卡片里", "templates/account/layout.html",
     '<section class="c-auth">', "<section>"),
    ("卡片样式没了圆角", "assets/css/input.css",
     "    border-radius: var(--radius-xl);\n    background-color: var(--tone-panel);\n  }\n\n  @media (min-width: 640px) {\n    .c-auth {",
     "    background-color: var(--tone-panel);\n  }\n\n  @media (min-width: 640px) {\n    .c-auth {"),
    ("注册以后可以用回粗线", WHY,
     '<p class="c-why__title">', '<p class="c-why__title border-t-2 border-fg">'),
    ("注册以后可以少一个图标", WHY,
     '<span class="c-why__icon c-quick__tile--lilac">{% include "components/icon.html" with name="shield" class="size-5" %}</span>',
     ""),
    ("报名页又带英文眉标", "tournaments/templates/tournaments/register.html",
     "      <h1>为战队报名</h1>", '      <p class="c-eyebrow">REGISTER</p>\n      <h1>为战队报名</h1>'),
    ("建队页又带英文眉标", "teams/templates/teams/create.html",
     "      <h1>创建战队</h1>", '      <p class="c-eyebrow">NEW TEAM</p>\n      <h1>创建战队</h1>'),
    ("前台别处画粗线", "templates/core/home.html",
     "{% block content %}", '{% block content %}<hr class="border-b-2">'),
    ("评论数借用旧样式", "comments/templates/comments/section.html",
     '<span class="c-count">{{ thread.total }}</span>',
     '<span class="c-comments__count">{{ thread.total }}</span>'),
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
