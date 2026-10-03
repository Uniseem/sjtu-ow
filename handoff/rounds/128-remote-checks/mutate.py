"""Round 128: break each new rule once and check its test goes red (AGENTS.md
rule 7). Runs the tests first and stops if they are not green (083).

bash scripts/remote-check.sh run uv run python handoff/rounds/128-remote-checks/mutate.py
"""

import os
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
PY = sys.executable
ENV = {**os.environ, "PYTHONUTF8": "1"}

T = "core/tests/test_check_script.py"
COMMANDS = f"{T}::test_every_ci_command_is_in_the_script"
ENVIRONMENT = f"{T}::test_the_script_sets_the_same_environment"

MUTATIONS = [
    ("no migration check", "scripts/check.sh",
     "uv run python manage.py makemigrations --check --dry-run\n", "\n", [COMMANDS]),
    ("no error page check", "scripts/check.sh",
     "git diff --exit-code -- deploy/error_pages\n", "\n", [COMMANDS]),
    ("no plain pytest", "scripts/check.sh",
     "  uv run pytest -q\n", "  true\n", [COMMANDS]),
    ("no ruff format", "scripts/check.sh",
     "uv run ruff format --check .\n", "\n", [COMMANDS]),
    ("the deploy check without the redirect", "scripts/check.sh",
     "  DJANGO_SECURE_SSL_REDIRECT=true", "  DJANGO_SECURE_SSL_REDIRECT=false",
     [ENVIRONMENT]),
    ("dev settings not chosen", "scripts/check.sh",
     "export DJANGO_SETTINGS_MODULE=sjtu_ow.settings.dev\n", "\n", [ENVIRONMENT]),
]


def run(tests):
    return subprocess.run(
        [PY, "-m", "pytest", "-q", "-x", "-p", "no:cacheprovider", *tests],
        cwd=ROOT, env=ENV, capture_output=True, text=True,
    ).returncode


def main():
    every = sorted({t for *_rest, tests in MUTATIONS for t in tests})
    assert run(every) == 0, "baseline is red"
    print("baseline green,", len(every), "tests")
    failed = []
    for label, rel, old, new, tests in MUTATIONS:
        path = ROOT / rel
        backup = path.with_suffix(path.suffix + ".mutbak")
        shutil.copy2(path, backup)
        try:
            raw = path.read_bytes().decode("utf-8")
            crlf = "\r\n" in raw
            text = raw.replace("\r\n", "\n")
            assert text.count(old) == 1, (label, text.count(old))
            text = text.replace(old, new)
            path.write_bytes((text.replace("\n", "\r\n") if crlf else text).encode("utf-8"))
            for test in tests:
                red = run([test]) != 0
                print(("caught " if red else "MISSED ") + label + " -> " + test.split("::")[1])
                if not red:
                    failed.append((label, test))
        finally:
            shutil.copy2(backup, path)
            backup.unlink()
            folder = rel.rsplit("/", 1)[0]
            for cache in ROOT.glob(folder + "/__pycache__/*.pyc"):
                cache.unlink()
    assert run(every) == 0, "not green after restoring"
    print("restored and green;", "missed:", failed or "none")
    return 1 if failed else 0


sys.exit(main())
