"""090 变异测试：逐条把规则改坏，跑对应测试，确认会红，再改回来。

在仓库根目录运行：uv run python handoff/rounds/090-cover-placeholders/mutate.py
"""

# ruff: noqa: E501 — 变异表原样写模板里的整段代码

import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
PY = sys.executable
ENV = {**os.environ, "PYTHONUTF8": "1", "PYTHONDONTWRITEBYTECODE": "1"}
T = "core/tests/test_cover_placeholders.py"

MUTATIONS = [
    (
        "文章卡片不用占位图",
        "templates/components/post_card.html",
        '{% else %}<img src="{{ article|cover_placeholder }}" width="640" height="360" alt="" loading="lazy">{% endif %}',
        "{% endif %}",
        [T, "content/tests/test_editorial_pages.py"],
    ),
    (
        "赛事卡片不用占位图",
        "templates/components/tournament_card.html",
        '{% else %}<img src="{{ tournament|cover_placeholder }}" width="640" height="360" alt="" loading="lazy">{% endif %}',
        "{% endif %}",
        [T],
    ),
    (
        "首页大图卡不用占位图",
        "content/templates/content/home_page.html",
        '{% else %}<img src="{{ feature.tournament|cover_placeholder }}" width="1280" height="720" class="c-feature__img" alt="">{% endif %}',
        "{% endif %}",
        [T],
    ),
    (
        "赛事横幅退回素色条",
        "tournaments/templates/tournaments/detail.html",
        '<header class="c-stage">',
        '<header class="c-stage{% if not tournament.cover %} c-stage--plain{% endif %}">',
        [T],
    ),
    (
        "赛事横幅不放占位图",
        "tournaments/templates/tournaments/detail.html",
        '{% else %}<img src="{{ tournament|cover_placeholder }}" width="2400" height="900" class="c-stage__img" alt="">{% endif %}',
        "{% endif %}",
        [T],
    ),
    (
        "文章头图不用占位图",
        "content/templates/content/article_page.html",
        '{% else %}<img src="{{ page|cover_placeholder }}" width="1408" height="792" alt="">{% endif %}',
        "{% endif %}",
        [T],
    ),
    (
        "有封面也用占位图（文章卡片）",
        "templates/components/post_card.html",
        "{% if article.cover %}",
        "{% if False %}",
        [T, "content/tests/test_editorial_pages.py"],
    ),
    (
        "有封面也用占位图（赛事）",
        "tournaments/templates/tournaments/detail.html",
        "{% if tournament.cover %}",
        "{% if False %}",
        [T],
    ),
    (
        "赛事和文章不错开",
        "core/placeholders.py",
        '"tournaments.tournament": 13',
        '"tournaments.tournament": 0',
        [T],
    ),
    (
        "每次随机取，不固定",
        "core/placeholders.py",
        "return ((obj.pk or 0) + offset) % len(CATALOGUE)",
        "return random.randrange(len(CATALOGUE))",
        [T],
    ),
    (
        "场景不交错排列",
        "core/placeholders.py",
        "CATALOGUE = [(style, variant) for variant in range(4) for style in STYLES]",
        "CATALOGUE = [(style, variant) for style in STYLES for variant in range(4)]",
        [T],
    ),
    (
        "改了画法没重新生成",
        "core/placeholders.py",
        "(0, 1), (0.25, 0.62), (0.5, 0.28)",
        "(0, 1), (0.25, 0.6), (0.5, 0.28)",
        [T],
    ),
    (
        "少一种场景",
        "core/placeholders.py",
        '    "forest": (\n',
        '    "_forest": (\n',
        [T],
    ),
    (
        "命令不删旧图",
        "core/management/commands/render_placeholders.py",
        "            path.unlink()\n",
        "            pass\n",
        [T],
    ),
    (
        "占位图里带脚本",
        "static/img/placeholders/cover-01.svg",
        "</svg>",
        "<script>alert(1)</script></svg>",
        [T],
    ),
]


def run(tests):
    result = subprocess.run(
        [PY, "-m", "pytest", "-q", "-p", "no:cacheprovider", "-x", *tests],
        cwd=ROOT,
        env=ENV,
        capture_output=True,
        text=True,
        encoding="utf-8",
    )
    return result.returncode, result.stdout.strip().splitlines()[-1]


code, line = run([T, "content/tests/test_editorial_pages.py"])
print(f"基线：{line}")
if code != 0:
    sys.exit("基线不是绿的，停下")

caught = 0
for name, rel, old, new, tests in MUTATIONS:
    path = ROOT / rel
    original = path.read_bytes()
    text = original.decode("utf-8")
    if text.count(old) != 1:
        print(f"!! {name}：找不到要改的那一处（{text.count(old)}）")
        continue
    path.write_bytes(text.replace(old, new).encode("utf-8"))
    try:
        code, line = run(tests)
    finally:
        path.write_bytes(original)
    ok = code != 0
    caught += ok
    print(f"{'抓到' if ok else '漏掉'}  {name}：{line}")

print(f"\n{caught}/{len(MUTATIONS)} 处变异被抓到")
code, line = run([T, "content/tests/test_editorial_pages.py"])
print(f"改回后：{line}")
