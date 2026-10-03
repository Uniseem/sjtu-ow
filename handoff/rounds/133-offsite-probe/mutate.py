"""Round 133: break each new rule once and check its test goes red (AGENTS.md
rule 7). Runs the tests first and stops if they are not green (083).

bash scripts/remote-check.sh run uv run python handoff/rounds/133-offsite-probe/mutate.py
"""

import os
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
PY = sys.executable
ENV = {**os.environ, "PYTHONUTF8": "1"}

T = "core/tests/test_offsite_backup.py"
CLEAN = f"{T}::test_the_probe_writes_then_cleans_up"
BEFORE = f"{T}::test_the_probe_works_before_uploading_is_on"
STEP = f"{T}::test_the_probe_says_which_step_failed"
BUTTON = f"{T}::test_the_settings_page_button"

MUTATIONS = [
    ("the probe file is left behind", "core/offsite.py",
     "        client.delete_object(Bucket=config.bucket, Key=key)\n", "        pass\n",
     [CLEAN]),
    ("half-filled settings are tried anyway", "core/offsite.py",
     "    if config.missing:\n        raise OffsiteError(f\"还缺这些设置",
     "    if False:\n        raise OffsiteError(f\"还缺这些设置", [STEP]),
    ("a failed write is not explained", "core/offsite.py",
     '        raise OffsiteError(f"写入「{config.bucket}」失败：{exc}") from exc\n',
     "        raise\n", [STEP]),
    ("a failed delete is not explained", "core/offsite.py",
     '            f"写入成功，但删除测试文件 {key} 失败：{exc}。"\n',
     '            f"失败：{exc}。"\n', [STEP]),
    ("no word about the missing key", "core/offsite.py",
     "    if not encryption_key():\n", "    if False:\n", [BEFORE]),
    ("no word about switching uploads on", "core/offsite.py",
     "    elif not config.enabled:\n", "    elif False:\n", [BEFORE]),
    ("anyone in the admin may run it", "core/views.py",
     '    from core import offsite\n\n    if not request.user.has_perm("core.change_sitesettings"):\n        raise PermissionDenied\n',
     "    from core import offsite\n\n", [BUTTON]),
    ("no button on the settings page", "templates/wagtailsettings/edit.html",
     "        <form method=\"post\" action=\"{% url 'core_try_offsite' %}\" class=\"w-mb-8\">\n",
     "        <form method=\"post\" action=\"\" class=\"w-mb-8\">\n", [BUTTON]),
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
