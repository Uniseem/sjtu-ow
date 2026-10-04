"""Round 184: break each new rule once and check its test goes red (AGENTS.md
rule 7). Runs the tests first and stops if they are not green (083).

bash scripts/remote-check.sh run uv run python handoff/rounds/184-superuser-email/mutate.py
"""

import os
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
PY = sys.executable
ENV = {**os.environ, "PYTHONUTF8": "1"}

T = "accounts/tests/test_superuser_email.py"


def t(name):
    return f"{T}::{name}"


RECORDED = t("test_the_command_records_the_email_as_verified")
SIGNS_IN = t("test_that_superuser_signs_in_without_a_code")
ALONE = t("test_superusers_already_there_are_left_alone")
STUCK = t("test_verify_email_lets_a_stuck_account_in")
UNKNOWN = t("test_verify_email_names_an_unknown_address")
CS = "accounts/management/commands/createsuperuser.py"
SV = "accounts/services.py"

MUTATIONS = [
    ("created superuser not trusted", CS, "            trust_email(user)\n", "            pass\n", [RECORDED, SIGNS_IN]),
    ("every superuser trusted", CS, "            .exclude(pk__in=before)\n", "", [ALONE]),
    ("address left unverified", SV, "            user=user, email=user.email, verified=True, primary=True\n", "            user=user, email=user.email, verified=False, primary=True\n", [RECORDED, SIGNS_IN]),
    ("existing address not verified", SV, "        address.verified = True\n", "        address.verified = address.verified\n", [STUCK]),
    ("old primary kept", SV, "    EmailAddress.objects.filter(user=user).exclude(email__iexact=user.email).update(\n        primary=False\n    )\n", "", [STUCK]),
    ("unknown address passes", "accounts/management/commands/verify_email.py", "        if user is None:\n            raise CommandError", "        if False:\n            raise CommandError", [UNKNOWN]),
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
