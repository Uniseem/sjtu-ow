"""Round 173: break each new rule once and check its test goes red (AGENTS.md
rule 7). Runs the tests first and stops if they are not green (083).

bash scripts/remote-check.sh run uv run python handoff/rounds/173-gone-applicants/mutate.py
"""

import os
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
PY = sys.executable
ENV = {**os.environ, "PYTHONUTF8": "1"}

T = "accounts/tests/test_gone_applicants.py"


def t(name):
    return f"{T}::{name}"


FATE = t("test_every_column_pointing_at_a_person_has_a_fate_on_deletion")
DISABLED = t("test_a_disabled_applicant_cannot_be_approved")
QUIET = t("test_no_reminder_or_letter_about_them")
DEAD = t("test_no_letter_goes_to_a_deleted_address")
TS = "teams/services.py"

MUTATIONS = [
    ("disabled people join", TS, "        gone = not application.applicant.is_active\n", "        gone = False\n", [DISABLED]),
    ("closed without a word", TS, '    if gone:\n        raise TeamError("申请人的账号已注销或停用，这条申请已关闭。")\n', "", [DISABLED]),
    ("captains still see them", TS, "            team=team, status=ApplicationStatus.PENDING, applicant__is_active=True\n", "            team=team, status=ApplicationStatus.PENDING\n", [DISABLED]),
    ("captains reminded of them", TS, "            team__disbanded_at__isnull=True,\n            applicant__is_active=True,\n", "            team__disbanded_at__isnull=True,\n", [QUIET]),
    ("the expiry letter goes anyway", TS, "        if application.applicant.is_active:\n            notifications.application_expired(application)\n", "        notifications.application_expired(application)\n", [QUIET]),
    ("letters to dead addresses", "core/letters.py", '        if address.endswith(".invalid"):\n            continue  # a deleted account (accounts.services.delete_account)\n', "", [DEAD]),
    ("a column without a fate", "accounts/services.py", '    "comments.CommentLike.user": "保留，只算在赞数里",\n', "", [FATE]),
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
