"""Round 144: break each new rule once and check its test goes red (AGENTS.md
rule 7). Runs the tests first and stops if they are not green (083).

bash scripts/remote-check.sh run uv run python handoff/rounds/144-tailwind-cli-cache/mutate.py
"""

import os
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
PY = sys.executable
ENV = {**os.environ, "PYTHONUTF8": "1"}

T = "core/tests/test_tailwind_cli_fetch.py"


def t(name):
    return f"{T}::{name}"


MUTATIONS = [
    ("the image pins another version", "Dockerfile",
     "ARG TAILWIND_CLI_VERSION=2.9.0\n", "ARG TAILWIND_CLI_VERSION=2.8.0\n",
     [t("test_the_image_pins_the_same_version_as_the_settings")]),
    ("the image downloads again", "Dockerfile",
     "    && uv run python manage.py tailwind build\n",
     "    && uv run python manage.py tailwind download_cli \\n    && uv run python manage.py tailwind build\n",
     [t("test_the_image_fetches_before_the_code_and_never_redownloads")]),
    ("the checks download every time", "scripts/check.sh",
     "ls .django_tailwind_cli/tailwindcss* >/dev/null 2>&1 ||\n  uv run",
     "uv run", [t("test_the_check_script_downloads_only_when_missing")]),
    ("no second try", "deploy/fetch_tailwind_cli.py",
     "ATTEMPTS = 5\n", "ATTEMPTS = 1\n", [t("test_a_flaky_download_is_retried")]),
    ("a name django-tailwind-cli does not know", "deploy/fetch_tailwind_cli.py",
     '    return f"tailwindcss-extra-linux-{arch(machine)}-{version}"\n',
     '    return f"tailwindcss-linux-{arch(machine)}-{version}"\n',
     [t("test_names_match_what_django_tailwind_cli_expects"), t("test_names_per_architecture")]),
    ("not executable", "deploy/fetch_tailwind_cli.py",
     "    os.chmod(target, 0o755)\n", "", [t("test_a_flaky_download_is_retried")]),
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
