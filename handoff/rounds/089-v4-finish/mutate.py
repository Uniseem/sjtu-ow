"""Break each new rule of round 089 once and check a test goes red.

    uv run python handoff/rounds/089-v4-finish/mutate.py

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
CSS = "assets/css/input.css"

MUTATIONS = [
    (
        "样式表里又出现 v3 名字",
        CSS,
        "  .c-link {\n    color: var(--color-primary-text);",
        "  .c-link {\n    color: var(--color-primary-deep);",
    ),
    (
        "模板里又用 v3 工具类",
        "templates/me/teams.html",
        "{% block me_content %}",
        '{% block me_content %}<span class="text-fg-red"></span>',
    ),
    (
        "样式表里又有小于 14px 的字",
        CSS,
        "  .c-rank {\n    display: inline-flex;\n    align-items: baseline;\n    gap: 0.25rem;\n    font-size: 0.875rem;",
        "  .c-rank {\n    display: inline-flex;\n    align-items: baseline;\n    gap: 0.25rem;\n    font-size: 0.8125rem;",
    ),
    (
        "模板里又用 text-xs",
        "templates/me/teams.html",
        "{% block me_content %}",
        '{% block me_content %}<span class="text-xs">x</span>',
    ),
    (
        "错误页深色少一个颜色",
        "static/css/error.css",
        "    --color-fg-3: #8f97a3;\n",
        "",
    ),
    (
        "错误页又带英文标签",
        "templates/errors/404.html",
        "{% extends",
        "{% comment %}NOT FOUND{% endcomment %}{% extends",
    ),
    (
        "评论数又是徽标",
        "comments/templates/comments/section.html",
        '<h2 id="comments">{% if thread.total %}{{ thread.total }} 条评论{% else %}评论{% endif %}</h2>',
        '<h2 id="comments">评论 <span class="c-count">{{ thread.total }}</span></h2>',
    ),
    (
        "又用回玻璃变量",
        CSS,
        "  .c-masthead {\n    position: sticky;",
        "  .c-masthead {\n    --glass-bg: var(--color-surface);\n    position: sticky;",
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
