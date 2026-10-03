"""Round 128: scripts/check.sh runs what CI runs (AGENTS.md「常用命令」).

The checks are written down twice, in .github/workflows/ci.yml and in the
script the test machine runs; this keeps the two from drifting apart.
"""

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
# The script tags its image sjtu-ow:check and installs its own way.
NOT_IN_SCRIPT = ("docker build", "uv sync")


def _ci():
    return (ROOT / ".github/workflows/ci.yml").read_text(encoding="utf-8")


def _script():
    return (ROOT / "scripts/check.sh").read_text(encoding="utf-8")


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
    return [c for c in commands if not c.startswith(("#", *NOT_IN_SCRIPT))]


def test_every_ci_command_is_in_the_script():
    commands = ci_commands()
    assert len(commands) >= 8, commands
    script = _script()
    missing = [command for command in commands if command not in script]
    assert not missing
    assert "docker build -q -t sjtu-ow:check ." in script


def test_the_script_sets_the_same_environment():
    pairs = re.findall(r"^\s+([A-Z][A-Z_]+): (.+)$", _ci(), flags=re.MULTILINE)
    assert len(pairs) >= 8, pairs
    script = _script()
    missing = [f"{k}={v}" for k, v in pairs if f"{k}={v.strip('"')}" not in script]
    assert not missing
