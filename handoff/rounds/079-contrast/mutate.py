"""Break each new rule of round 079 once and check a test goes red.

    uv run python handoff/rounds/079-contrast/mutate.py

The tests read assets/css/input.css directly, so app.css is not rebuilt.
"""

import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
TESTS = ["core/tests/test_design_system.py"]
CSS = "assets/css/input.css"

MUTATIONS = [
    ("ink-3 改回 3.75:1 的旧值", CSS,
     "--color-ink-3: #726a68;", "--color-ink-3: #847c7a;"),
    ("控件边框用回 2:1 的浅灰", CSS,
     "--color-control: #847c7a;", "--color-control: #b6b0ae;"),
    ("深色上的控件边框太浅", CSS,
     "--color-night-control: #736a69;", "--color-night-control: #5a5150;"),
    ("深色上的第三级文字太暗", CSS,
     "--color-night-ink-3: #8f8785;", "--color-night-ink-3: #847c7a;"),
    ("深色区块又写死第三级文字", CSS,
     "--tone-fg-3: var(--color-night-ink-3);", "--tone-fg-3: #847c7a;"),
    ("深色区块不翻转控件边框", CSS,
     "  --tone-control: var(--color-night-control);\n", ""),
    ("深色状态色又写死", CSS,
     "color: var(--color-ok-bright);", "color: #7cc093;"),
    ("输入框用回装饰线", CSS,
     "    padding: 0.5rem 0.75rem;\n    border: 1px solid var(--tone-control);",
     "    padding: 0.5rem 0.75rem;\n    border: 1px solid var(--tone-line-strong);"),
    ("复选框用回装饰线", CSS,
     "border: 1.5px solid var(--tone-control);", "border: 1.5px solid var(--tone-line-strong);"),
    ("页头搜索框用回发丝线", CSS,
     "    padding: 0 2.25rem 0 0.75rem;\n    border: 1px solid var(--tone-control);",
     "    padding: 0 2.25rem 0 0.75rem;\n    border: 1px solid var(--tone-line);"),
    ("样张页色块还写旧值", "core/styleguide.py",
     '("墨 3", "ink-3", "bg-ink-3", "#726A68")', '("墨 3", "ink-3", "bg-ink-3", "#847C7A")'),
    ("样张页漏掉新令牌", "core/styleguide.py",
     '    ("夜控件边框", "night-control", "bg-night-control", "#736A69"),\n', ""),
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
