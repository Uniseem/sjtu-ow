"""Break each new rule of round 075 once and check a test goes red.

    uv run python handoff/rounds/075-home-and-content/mutate.py
"""

import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
TESTS = [
    "content/tests/test_home_sections.py",
    "scrims/tests/test_home_listing.py",
    "tournaments/tests/test_public_pages.py",
]

MUTATIONS = [
    ("近期不按日期合并", "content/home.py",
     "    entries.sort(key=lambda entry: entry.moment)\n", ""),
    ("近期不限 4 条", "content/home.py",
     "    return entries[:limit]\n", "    return entries\n"),
    ("近期的标签对调", "content/home.py",
     'Agenda("scrim", item, item.starts_at, "开始")', 'Agenda("scrim", item, item.starts_at, "截止")'),
    ("日程带多一天", "content/home.py",
     "    last = today + timedelta(days=days - 1)\n", "    last = today + timedelta(days=days)\n"),
    ("日程带数进草稿和取消的内战", "content/home.py",
     "        status__in=[ScrimStatus.PUBLISHED, ScrimStatus.FINISHED],\n        starts_at__date__gte=today,",
     "        starts_at__date__gte=today,"),
    ("日程带不数赛事", "content/home.py",
     "        by_date[timezone.localdate(tournament.starts_at)].tournaments.append(tournament)\n", "        pass\n"),
    ("日程带数进草稿赛事", "content/home.py",
     "        status__in=[TournamentStatus.PUBLISHED, TournamentStatus.FINISHED],\n", ""),
    ("今天标错一天", "content/home.py",
     "Day(today + timedelta(days=offset), offset == 0)", "Day(today + timedelta(days=offset), offset == 1)"),
    ("内战列表留着已结束的", "content/home.py",
     "if scrim.status == ScrimStatus.PUBLISHED and scrim.starts_at >= now", "if scrim.starts_at >= now"),
    ("即将开放的排在报名中前面", "content/home.py",
     '    items = [("open", item) for item in groups["open"]]\n    items += [("upcoming", item) for item in groups["upcoming"]]\n',
     '    items = [("upcoming", item) for item in groups["upcoming"]]\n    items += [("open", item) for item in groups["open"]]\n'),
    ("赛场赛事不限 3 个", "content/home.py",
     "    return items[:limit]\n", "    return items\n"),
    ("同栏目最新含本篇", "content/models.py",
     "            .exclude(pk=self.pk)\n", ""),
    ("同栏目最新混进别的栏目", "content/models.py",
     "            .filter(category_id=self.category_id)\n", ""),
    ("同栏目最新取 6 篇", "content/models.py",
     "RELATED_ARTICLE_COUNT = 4", "RELATED_ARTICLE_COUNT = 6"),
    ("正文不包 c-prose", "content/templates/content/article_page.html",
     '<div class="c-prose">', "<div>"),
    ("文章页不显示封面", "content/templates/content/article_page.html",
     '{% image page.cover fill-1200x675 class="w-full bg-sunken" alt="" %}', ""),
    ("草稿赛事也挂在文章下面", "content/templates/content/article_page.html",
     "{% if page.tournament and page.tournament.is_public %}", "{% if page.tournament %}"),
    ("分类标签不标当前项", "content/templates/content/article_index_page.html",
     '{% if active_category == category.slug %} aria-current="page"{% endif %}', ""),
    ("没有焦点图也加载脚本", "content/templates/content/home_page.html",
     "  {% if carousel %}<script src=\"{% static 'js/carousel.js' %}\" defer></script>{% endif %}",
     "  <script src=\"{% static 'js/carousel.js' %}\" defer></script>"),
    ("焦点图索引不编号", "content/templates/content/home_page.html",
     '<span class="num">{{ forloop.counter|ow_index }}</span>', '<span class="num">{{ forloop.counter }}</span>'),
    ("赛场票根不显示通过的队数", "content/templates/content/home_page.html",
     "with tournament=tournament show_count=True approved=", "with tournament=tournament approved="),
    ("战队图块不写人数", "templates/components/team_tile.html",
     '{% if team.member_count %}<span class="font-numeric">{{ team.member_count }} 人</span>{% endif %}', ""),
    ("近期混进 7 天后的内战", "content/models.py",
     '        context["next_up"] = home.next_up(\n            context["open_tournaments"], context["upcoming_scrims"]\n        )',
     '        context["next_up"] = home.next_up(\n            context["open_tournaments"], home.strip_scrims(home.day_strip())\n        )'),
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
                [sys.executable, "-m", "pytest", "-q", "-x", *TESTS],
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
