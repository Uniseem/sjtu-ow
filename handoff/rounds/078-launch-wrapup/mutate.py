"""Break each new rule of round 078 once and check a test goes red.

    uv run python handoff/rounds/078-launch-wrapup/mutate.py
"""

import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
TESTS = [
    "content/tests/test_content.py",
    "teams/tests/test_teams.py",
    "core/tests/test_design_system.py",
]

MUTATIONS = [
    ("保留片段漏掉 search", "content/models.py", '        "search",\n', ""),
    ("保留片段漏掉 registrations", "content/models.py", '        "registrations",\n', ""),
    ("保留片段漏掉 Caddy 的 static", "content/models.py", '        "static",\n', ""),
    ("入队申请表单还叫重装", "teams/forms.py",
     'role_tank = forms.BooleanField(label="坦克"', 'role_tank = forms.BooleanField(label="重装"'),
    ("给队长的邮件还叫重装", "teams/models.py",
     'labels.append("坦克")', 'labels.append("重装")'),
    ("标签条不滚到当前项", "static/js/app.js",
     "      strips[s].scrollLeft = current.offsetLeft - strips[s].offsetLeft - 16;\n", ""),
    ("手机标签条不标当前项", "templates/me/_nav.html",
     '<a href="{% url name %}"{% if current_me == name %} aria-current="page"{% endif %}>{{ label }}</a>',
     '<a href="{% url name %}">{{ label }}</a>'),
]


def clear_pycache():
    for path in ROOT.rglob("__pycache__"):
        if ".venv" in path.parts:
            continue
        shutil.rmtree(path, ignore_errors=True)


def main():
    killed = 0
    for label, rel, old, new in MUTATIONS:
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
