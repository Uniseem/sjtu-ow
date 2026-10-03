"""Round 150: break each new rule once and check its test goes red (AGENTS.md
rule 7). Runs the tests first and stops if they are not green (083).

bash scripts/remote-check.sh run uv run python handoff/rounds/150-lost-mail/mutate.py
"""

import os
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
PY = sys.executable
ENV = {**os.environ, "PYTHONUTF8": "1"}

T = "core/tests/test_admin_functions.py::test_the_owner_hears_about_mail_that_never_went_out"
TODO = "core/admin_todo.py"

MUTATIONS = [
    ("retries still coming count too", TODO,
     "        if _attempt(args_kwargs) >= len(MAIL_RETRY_DELAYS)\n", "        if True\n", [T]),
    ("old failures count too", TODO,
     "            finished_at__gte=(now or timezone.now()) - MAIL_LOOKBACK,\n", "", [T]),
    ("sent mail counts too", TODO,
     "            status=TaskResultStatus.FAILED,\n", "", [T]),
    ("no error shown", TODO,
     '                f"（{error}），检查全站设置里的 SMTP，先发一封测试邮件",\n',
     '                "，检查全站设置里的 SMTP，先发一封测试邮件",\n', [T]),
    ("no line at all", TODO,
     "    if lost:\n        rows.append(\n", "    if False:\n        rows.append(\n", [T]),
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
