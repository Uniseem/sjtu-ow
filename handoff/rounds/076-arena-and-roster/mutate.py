"""Break each new rule of round 076 once and check a test goes red.

    uv run python handoff/rounds/076-arena-and-roster/mutate.py
"""

import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
TESTS = ["core/tests/test_arena_pages.py", "scrims/tests/test_home_listing.py"]

MUTATIONS = [
    ("报名中的赛事也用表格", "tournaments/templates/tournaments/index.html",
     '{% if phase == "open" or phase == "upcoming" %}', '{% if phase == "upcoming" %}'),
    ("阶段数量只数报名中", "tournaments/views.py",
     '"phase_counts": [(label, len(items)) for _phase, label, items in groups],',
     '"phase_counts": [(label, len(groups[0][2])) for _phase, label, items in groups],'),
    ("待审的也算进已通过", "tournaments/services.py",
     "            tournament_id__in=[item.pk for item in tournaments],\n            status=RegistrationStatus.APPROVED,\n",
     "            tournament_id__in=[item.pk for item in tournaments],\n"),
    ("详情页不写个人报名人数", "tournaments/templates/tournaments/detail.html",
     '<div class="c-stat"><span class="c-stat__label">个人报名</span>', '<div class="c-stat"><span class="c-stat__label">散人</span>'),
    ("详情页已通过写成散人数", "tournaments/templates/tournaments/detail.html",
     '<span class="c-stat__value">{{ approved_teams|length }}<small>队</small>', '<span class="c-stat__value">{{ pool_counts.total }}<small>队</small>'),
    ("内战报名人数不按内战分", "scrims/services.py",
     '        ScrimSignup.objects.filter(scrim_id__in=[item.pk for item in scrims])\n        .values("scrim_id")',
     '        ScrimSignup.objects.all()\n        .values("scrim_id")'),
    ("列表的名额格不画", "templates/components/scrim_ticket.html",
     "{% if show_slots %}", "{% if False %}"),
    ("已结束的内战也算即将开始", "scrims/views.py",
     "    upcoming = [item for item in scrims if item.status == ScrimStatus.PUBLISHED]\n",
     "    upcoming = list(scrims)\n"),
    ("战队图块不写上限", "teams/templates/teams/index.html",
     "with members=team.members_total capacity=max_members show_closed=True", "with members=team.members_total show_closed=True"),
    ("招募中的总数不过滤", "teams/services.py",
     'recruiting_total=Count("id", filter=Q(is_recruiting=True)),', 'recruiting_total=Count("id"),'),
    ("战队页不写成立日期", "teams/templates/teams/detail.html",
     '<span>成立于 <time class="font-numeric" datetime="{{ team.created_at|date:\'c\' }}">{{ team.created_at|ow_date }}</time></span>', ""),
    ("名册编号从 000 开始", "members/templates/members/index.html",
     '{{ forloop.counter|stringformat:"03d" }}', '{{ forloop.counter0|stringformat:"03d" }}'),
    ("报名截止时不刷新", "scrims/services.py",
     "    runs += [(scrim.signup_deadline, status_pages), (scrim.starts_at, status_pages)]\n",
     "    runs += [(scrim.starts_at, status_pages)]\n"),
    ("开始时只刷新首页", "scrims/services.py",
     '    status_pages = ["/", "/scrims/", f"/scrims/{scrim.pk}/"]\n', '    status_pages = ["/"]\n'),
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
