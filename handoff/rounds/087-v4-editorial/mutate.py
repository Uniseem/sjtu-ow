"""Break each new rule of round 087 once and check a test goes red.

    uv run python handoff/rounds/087-v4-editorial/mutate.py

The baseline is run first: a red baseline makes every mutation look killed
(round 083).
"""

import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
TESTS = [
    "content/tests/test_editorial_pages.py",
    "content/tests/test_home_sections.py",
    "search/tests/test_search.py",
]
CSS = "assets/css/input.css"
CARD = "templates/components/post_card.html"

MUTATIONS = [
    (
        "没封面时又画渐变",
        CARD,
        '<span class="c-media__none">{{ article.category.name|default:"资讯" }}</span>',
        '<span class="c-hatch"></span>',
    ),
    (
        "资讯列表不显示摘要",
        "content/templates/content/article_index_page.html",
        '{% include "components/post_card.html" with summary=True %}',
        '{% include "components/post_card.html" %}',
    ),
    (
        "筛选的当前项不是红色下划线",
        CSS,
        "    height: 2px;\n    background-color: var(--color-primary);\n  }\n\n  .c-tabs__count {",
        "    height: 2px;\n    background-color: var(--color-fg);\n  }\n\n  .c-tabs__count {",
    ),
    (
        "文章栏不居中",
        CSS,
        "    max-width: calc(var(--container-prose) + 2rem);\n    margin-inline: auto;",
        "    max-width: calc(var(--container-prose) + 2rem);",
    ),
    (
        "同栏目最新取 4 篇",
        "content/models.py",
        "RELATED_ARTICLE_COUNT = 3",
        "RELATED_ARTICLE_COUNT = 4",
    ),
    (
        "关于三页不标当前页",
        "content/templates/content/standard_page.html",
        '<a href="/privacy/"{% if request.path == "/privacy/" %} aria-current="page"{% endif %}>',
        '<a href="/privacy/">',
    ),
    (
        "搜索结果又带数量徽标",
        "search/templates/search/results.html",
        '<h2 id="search-{{ forloop.counter }}">{{ group.label }}</h2>',
        '<h2 id="search-{{ forloop.counter }}">{{ group.label }}</h2><span class="c-count">{{ group.hits|length }}</span>',
    ),
    (
        "搜索栏下又写说明小字",
        "search/templates/search/results.html",
        "      </form>\n    </div>\n  </header>",
        '      </form>\n      <p class="c-pagehead__meta">多个词用空格隔开。</p>\n    </div>\n  </header>',
    ),
    (
        "引用又填底色",
        CSS,
        "    border-left: 3px solid var(--color-line);\n    color: var(--color-fg-2);",
        "    border-left: 3px solid var(--color-line);\n    background-color: var(--color-surface-2);\n    color: var(--color-fg-2);",
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
