"""Break each new rule of round 083 once and check a test goes red.

    uv run python handoff/rounds/083-editorial-pages/mutate.py
"""

import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
TESTS = ["content/tests/test_editorial_pages.py"]
ARTICLE = "content/templates/content/article_page.html"
SEARCH = "search/templates/search/results.html"
INDEX = "content/templates/content/article_index_page.html"

MUTATIONS = [
    ("没封面的卡片用回同一种渐变", "templates/components/post_card.html",
     '{% include "components/category_wash.html" with category=article.category %}',
     '<span class="c-hatch" aria-hidden="true"></span>'),
    ("占位里没有分类图标", "templates/components/category_wash.html",
     '{% else %}{% include "components/icon.html" with name="news" class="c-hatch__icon" %}{% endif %}',
     "{% else %}{% endif %}"),
    ("有封面的卡片也盖上占位", "templates/components/post_card.html",
     "{% if article.cover %}", "{% if False %}"),
    ("资讯列表用回一行一篇", INDEX,
     '<ol class="c-posts" data-reveal>', '<ol class="c-rowlist">'),
    ("选中的筛选标签没有对勾", "assets/css/input.css",
     "  .c-tabs a[aria-current]::before {", "  .c-tabs a[aria-current]::after {"),
    ("文章元信息没有作者头像", ARTICLE,
     '<span class="c-avatar c-avatar--sm" aria-hidden="true">{{ page.author.nickname|initial }}</span>\n            <span class="font-semibold',
     '<span class="font-semibold'),
    ("文末用回资料表", ARTICLE,
     '<aside class="c-byline" aria-label="文章信息">',
     '<aside class="c-facts" aria-label="文章信息">'),
    ("同栏目最新用回粗线", ARTICLE,
     '<h2 id="article-related">', '<h2 id="article-related" class="border-b-2 border-fg">'),
    ("搜索框用回深色边框", SEARCH,
     'class="c-searchbar">', 'class="c-searchbar border-fg">'),
    ("搜索结果组没有数量徽标", SEARCH,
     '<span class="c-count">{{ group.hits|length }}</span>',
     "<span>{{ group.hits|length }}</span>"),
    ("资讯页又带英文眉标", INDEX,
     "        <div>\n          <h1>{{ page.title }}</h1>",
     '        <div>\n          <p class="c-eyebrow">NEWS</p>\n          <h1>{{ page.title }}</h1>'),
    ("关于页侧栏又带英文", "templates/components/about_side.html",
     '<p class="c-sidenav__title">关于本站</p>',
     '<p class="c-sidenav__title">ABOUT · 关于本站</p>'),
]


def clear_pycache():
    for path in ROOT.rglob("__pycache__"):
        if ".venv" in path.parts:
            continue
        shutil.rmtree(path, ignore_errors=True)


def main(only=None):
    killed = 0
    for label, rel, old, new in MUTATIONS:
        if only and only not in label:
            continue
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
    main(sys.argv[1] if len(sys.argv) > 1 else None)
