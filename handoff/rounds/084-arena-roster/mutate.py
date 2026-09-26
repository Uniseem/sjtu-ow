"""Break each new rule of round 084 once and check a test goes red.

    uv run python handoff/rounds/084-arena-roster/mutate.py

The baseline is run first: a red baseline makes every mutation look killed
(round 083).
"""

import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
TESTS = ["core/tests/test_arena_v3.py"]
T = "tournaments/templates/tournaments/"
S = "scrims/templates/scrims/"
MEMBERS = "members/templates/members/index.html"

MUTATIONS = [
    ("赛事页又带英文眉标", T + "index.html",
     "      <h1>赛事</h1>", '      <p class="c-eyebrow">TOURNAMENTS</p>\n      <h1>赛事</h1>'),
    ("成员页又带英文眉标", MEMBERS,
     "      <h1>成员展示</h1>", '      <p class="c-eyebrow">MEMBERS</p>\n      <h1>成员展示</h1>'),
    ("内战区块头借用评论计数", S + "index.html",
     '<span class="c-count">{{ upcoming|length }}</span>',
     '<span class="c-comments__count">{{ upcoming|length }}</span>'),
    ("赛事资料表不在卡片里", T + "detail.html",
     '<dl class="c-facts c-facts--card">', '<dl class="c-facts">'),
    ("战队资料表不在卡片里", "teams/templates/teams/detail.html",
     '<dl class="c-facts c-facts--card">', '<dl class="c-facts">'),
    ("相关文章用回粗线", T + "detail.html",
     '<h2 id="t-articles">', '<h2 id="t-articles" class="border-b-2 border-fg">'),
    ("位置统计用回上下横线", S + "detail.html",
     '<div class="c-rolestats">', '<div class="grid grid-cols-3 border-y border-rule">'),
    ("成员数又被拆开", MEMBERS,
     '<p class="c-pagehead__meta"><span>共 <span class="font-numeric">{{ members|length }}</span> 位成员</span></p>',
     '<p class="c-pagehead__meta">共 <span class="font-numeric">{{ members|length }}</span> 位成员</p>'),
    ("名册不编号", MEMBERS,
     '{{ forloop.counter|stringformat:"03d" }}', "{{ forloop.counter }}"),
    ("名册卡片没有头像", MEMBERS,
     '                <span class="c-avatar" aria-hidden="true">{{ member.user.nickname|initial }}</span>\n                <span class="min-w-0">\n                  <span class="c-roster__name">',
     '                <span class="min-w-0">\n                  <span class="c-roster__name">'),
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
