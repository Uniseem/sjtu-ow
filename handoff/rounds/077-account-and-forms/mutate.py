"""Break each new rule of round 077 once and check a test goes red.

    uv run python handoff/rounds/077-account-and-forms/mutate.py
"""

import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
TESTS = ["core/tests/test_design_system.py"]

MUTATIONS = [
    ("模板里又写 daisyUI 的按钮", "templates/me/security.html",
     'class="c-btn c-btn--secondary">修改密码', 'class="btn btn-outline">修改密码'),
    ("模板里又写 daisyUI 的底色", "teams/templates/teams/manage.html",
     '<li class="c-panel">', '<li class="c-panel bg-base-200">'),
    ("样式表又加载 daisyUI", "assets/css/input.css",
     '@source "../../templates/**/*.html";', '@plugin "daisyui";\n@source "../../templates/**/*.html";'),
    ("导航按子串判断当前栏目", "templates/components/main_nav.html",
     '{% if p|slice:":7" == "/teams/" %}', '{% if "/teams/" in p %}'),
    ("个人中心菜单不编号", "templates/me/_nav.html",
     '<span class="c-sidenav__index">{{ forloop.counter|ow_index }}</span>', ""),
    ("个人中心菜单不标当前项", "templates/me/_nav.html",
     '<a href="{% url name %}"{% if current_me == name %} aria-current="page"{% endif %}><span', '<a href="{% url name %}"><span'),
    ("段位小段不用数字字体", "templates/components/rank_badge.html",
     '<span class="c-rank__div">{{ parts.1 }}</span>', "{{ parts.1 }}"),
    ("待审核也画成对勾", "templates/components/registration_status.html",
     '{% elif registration.status == "pending" %}{% include "components/status_badge.html" with kind="warn"',
     '{% elif registration.status == "pending" %}{% include "components/status_badge.html" with kind="ok"'),
    ("撤回画成驳回", "templates/components/registration_status.html",
     '{% else %}{% include "components/status_badge.html" with kind="off"', '{% else %}{% include "components/status_badge.html" with kind="rejected"'),
]


def build_css():
    subprocess.run(
        [sys.executable, "manage.py", "tailwind", "build", "--force"],
        cwd=ROOT,
        capture_output=True,
    )


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
        if rel.endswith(".css"):
            build_css()
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
            if rel.endswith(".css"):
                build_css()
        summary = result.stdout.strip().splitlines()[-1] if result.stdout else ""
        if result.returncode != 0:
            killed += 1
            print(f"KILLED   {label}  | {summary}")
        else:
            print(f"SURVIVED {label}  | {summary}")
    print(f"{killed}/{len(MUTATIONS)} killed")


if __name__ == "__main__":
    main()
