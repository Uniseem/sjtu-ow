"""Break each new rule of round 088 once and check a test goes red.

    uv run python handoff/rounds/088-v4-arena/mutate.py

The baseline is run first: a red baseline makes every mutation look killed
(round 083).
"""

import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
TESTS = [
    "core/tests/test_arena_pages.py",
    "core/tests/test_arena_v3.py",
    "core/tests/test_design_system.py",
    "teams/tests/test_teams.py",
]
T = "tournaments/templates/tournaments/"
S = "scrims/templates/scrims/"

MUTATIONS = [
    (
        "报名放回横幅里",
        T + "detail.html",
        '        <section class="c-panel" aria-label="报名">\n          {% include "tournaments/slots/actions.html" %}\n        </section>\n',
        "",
    ),
    (
        "资料表不在面板里",
        S + "detail.html",
        '<dl class="c-facts c-panel">',
        '<dl class="c-facts">',
    ),
    (
        "内战区块头又带数量徽标",
        S + "index.html",
        '<h2 id="scrims-upcoming">即将开始</h2>',
        '<h2 id="scrims-upcoming">即将开始</h2><span class="c-count">{{ upcoming|length }}</span>',
    ),
    (
        "赛事栏目头又带统计条",
        T + "index.html",
        "      <h1>赛事</h1>\n",
        '      <h1>赛事</h1>\n      <div class="c-factbar"><div class="c-stat"><span class="c-stat__value">1</span></div></div>\n',
    ),
    (
        "内战列表行没有进度条",
        "templates/components/scrim_row.html",
        '    <progress class="c-meter"',
        '    <meter class="c-meter"',
    ),
    (
        "赛事卡数上待审的队",
        "templates/components/tournament_card.html",
        " · 已通过 {{ approved|default:0 }} 队",
        " · 已报名 队",
    ),
    (
        "战队格每支队多查一次",
        "templates/components/team_tile.html",
        "{% if members %}{{ members }}{% else %}{{ team.member_count }}{% endif %}",
        "{{ members|default:team.member_count }}",
    ),
    (
        "位置统计不是三格",
        S + "detail.html",
        '<dl class="c-rolestats">',
        '<dl class="c-rolestats-old">',
    ),
    (
        "横幅图上不压暗色",
        "assets/css/input.css",
        "  .c-stage:not(.c-stage--plain)::after {\n    content: \"\";\n    position: absolute;\n    inset: 0;\n    background-image: linear-gradient(",
        "  .c-stage:not(.c-stage--plain)::after {\n    content: \"\";\n    position: absolute;\n    inset: 0;\n    background-image: none, (",
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
