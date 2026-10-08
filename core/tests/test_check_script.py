"""scripts/check.sh 和 CI、测试机整组说的是同一件事（128 起，229 起只剩新栈）。"""

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
GONE = ("uv run pytest", "ruff check", "manage.py", "docker build", "CHECK_LEGACY", "CHECK_DOCKER")


def _ci():
    return (ROOT / ".github/workflows/ci.yml").read_text(encoding="utf-8")


def _script():
    return (ROOT / "scripts/check.sh").read_text(encoding="utf-8")


def _remote():
    return (ROOT / "scripts/remote-check.sh").read_text(encoding="utf-8")


def ci_commands():
    commands, block = [], None
    for line in _ci().splitlines():
        stripped = line.strip()
        if block is not None:
            if stripped and len(line) - len(line.lstrip()) > block:
                commands.append(stripped)
                continue
            block = None
        match = re.match(r"(\s*)(?:- )?run:\s*(.*)$", line)
        if match:
            rest = match.group(2).strip()
            if rest == "|":
                block = len(match.group(1))
            elif rest:
                commands.append(rest)
    return [c for c in commands if not c.startswith("#")]


def test_every_ci_command_is_in_the_script():
    commands = ci_commands()
    assert len(commands) >= 5, commands
    script = _script()
    missing = [command for command in commands if command not in script]
    assert not missing


def test_ci_and_the_test_machine_skip_the_old_stack():
    for name, text in (("CI", _ci()), ("check.sh", _script()), ("remote-check.sh", _remote())):
        for gone in GONE:
            assert gone not in text, f"{name} 还有 {gone}"
    assert "sh scripts/check.sh" in _remote()
