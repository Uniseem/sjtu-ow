"""Break each new rule of round 082 once and check a test goes red.

    uv run python handoff/rounds/082-home-v3/mutate.py
"""

import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
TESTS = [
    "content/tests/test_home_sections.py",
    "core/tests/test_design_system.py",
    "tournaments/tests/test_public_pages.py",
]
HOME = "content/home.py"
TEMPLATE = "content/templates/content/home_page.html"
CSS = "assets/css/input.css"

MUTATIONS = [
    ("成立时长不看今年的周年到没到", HOME,
     "        years -= 1\n", "        pass\n"),
    ("闰年 2 月 29 日的周年算错", HOME,
     "return founded.replace(year=year, day=28)", "return founded.replace(year=year, month=3, day=1)"),
    ("未来的成立日期也显示", HOME,
     "    if founded > today:\n        return None\n", ""),
    ("QQ 群链接允许 http://", "core/models.py",
     'value.lower().startswith("https://")', 'value.lower().startswith("http")'),
    ("没填 QQ 群链接也显示那块", TEMPLATE,
     "{% if qq_group_url %}", "{% if True %}"),
    ("没填成立日期也显示「社区已成立」", TEMPLATE,
     "{% if age %}\n            <div data-figure=\"age\">", "{% if True %}\n            <div data-figure=\"age\">"),
    ("通知公告混进攻略", HOME,
     'NOTICE_CATEGORIES = ("notice", "event-notice")', 'NOTICE_CATEGORIES = ("notice", "event-notice", "guide")'),
    ("累计内战把还没办的也算上", HOME,
     '"scrims": Scrim.objects.filter(status=ScrimStatus.FINISHED).count(),',
     '"scrims": Scrim.objects.exclude(status=ScrimStatus.DRAFT).count(),'),
    ("进度条的上限写死", HOME,
     "entry.capacity = entry.item.players_needed", "entry.capacity = 12"),
    ("资讯头条后面只列四篇", HOME,
     '"news_rest": news[1:],', '"news_rest": news[2:],'),
    ("战队数把解散的也算上", HOME,
     "    return services.active_teams().count()", "    from teams.models import Team\n\n    return Team.objects.count()"),
    ("内战报名不刷新首页", "scrims/services.py",
     '        prerender.request_page(f"/scrims/{scrim.pk}/", kind="scrim")\n        prerender.request_page("/", kind="home")',
     '        prerender.request_page(f"/scrims/{scrim.pk}/", kind="scrim")'),
    ("报名通过不刷新首页", "tournaments/registration.py",
     '    )\n    prerender.request_page("/", kind="home")\n    if registration.team_id:',
     '    )\n    if registration.team_id:'),
    ("邮箱验证只刷新成员页", "members/signals.py",
     '    if not raw:\n        refresh_member_count()', '    if not raw:\n        refresh_page()'),
    ("账号停用只刷新成员页", "members/signals.py",
     '        return\n    refresh_member_count()', '        return\n    refresh_page()'),
    ("QQ 群链接改了不刷新首页", "core/signals.py",
     'HOMEPAGE_FIELDS = ("founded_on", "qq_group_url")', 'HOMEPAGE_FIELDS = ("founded_on",)'),
    ("改任何设置都刷新首页", "core/signals.py",
     "    if before is not None and before == now:\n        return\n", ""),
    ("减少动态效果时还留着动画延迟", CSS,
     "      animation-delay: 0s !important;\n", ""),
    ("首页网格的列能被内容撑宽", CSS,
     "    grid-template-columns: minmax(0, 1fr);\n    gap: 1.5rem;\n  }\n\n  @media (min-width: 1024px) {\n    .c-homegrid {",
     "    gap: 1.5rem;\n  }\n\n  @media (min-width: 1024px) {\n    .c-homegrid {"),
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
                [sys.executable, "-m", "pytest", "-q", "-x", "-p", "no:randomly", *TESTS],
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
