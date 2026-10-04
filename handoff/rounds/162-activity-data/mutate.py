"""Round 162: break each new rule once and check its test goes red (AGENTS.md
rule 7). Runs the tests first and stops if they are not green (083).

bash scripts/remote-check.sh run uv run python handoff/rounds/162-activity-data/mutate.py
"""

import os
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
PY = sys.executable
ENV = {**os.environ, "PYTHONUTF8": "1"}

T = "core/tests/test_activity.py"


def t(name):
    return f"{T}::{name}"


MONTH = t("test_the_months_numbers")
PERIODS = t("test_the_periods")
OFFICERS = t("test_officers_see_it_and_can_take_the_table_away")
WRITERS = t("test_writers_do_not")
A = "core/activity.py"

MUTATIONS = [
    ("cancelled scrims count", A, "        status__in=[ScrimStatus.PUBLISHED, ScrimStatus.FINISHED],\n", "        status__in=[ScrimStatus.PUBLISHED, ScrimStatus.FINISHED, ScrimStatus.CANCELLED],\n", [MONTH]),
    ("the next day's midnight counts", A, "        starts_at__lt=period.until,\n", "        starts_at__lte=period.until,\n", [MONTH]),
    ("the last day is cut off", A, "            datetime.combine(self.end + timedelta(days=1), time.min)\n", "            datetime.combine(self.end, time.min)\n", [MONTH]),
    ("undated tournaments vanish", A, 'Coalesce("starts_at", "registration_closes_at")', 'Coalesce("starts_at", "starts_at")', [MONTH]),
    ("cancelled tournaments count", A, "            status__in=[TournamentStatus.PUBLISHED, TournamentStatus.FINISHED]\n", "            status__in=[TournamentStatus.PUBLISHED, TournamentStatus.FINISHED, TournamentStatus.CANCELLED]\n", [MONTH]),
    ("rejected rosters play", A, "        registration__status=RegistrationStatus.APPROVED,\n", "", [MONTH]),
    ("everyone signed up played", A, '        players=Count("signups", filter=Q(signups__is_selected=True)),\n', '        players=Count("signups"),\n', [MONTH]),
    ("rejected teams count", A, "            filter=Q(registrations__status=RegistrationStatus.APPROVED),\n", "", [MONTH]),
    ("scrim people counted twice", A, '        "scrim_people": ScrimSignup.objects.filter(scrim__in=_scrims(period))\n        .values("user")\n        .distinct()\n', '        "scrim_people": ScrimSignup.objects.filter(scrim__in=_scrims(period))\n        .values("user")\n', [MONTH]),
    ("tournament people counted twice", A, '        "tournament_people": _players(_tournaments(period))\n        .values("user")\n        .distinct()\n', '        "tournament_people": _players(_tournaments(period))\n        .values("user")\n', [MONTH]),
    ("hidden comments count", A, "            is_hidden=False,\n", "", [MONTH]),
    ("deleted comments count", A, "            is_deleted=False,\n", "", [MONTH]),
    ("everyone is from SJTU", A, '"sjtu_members": newcomers.filter(is_sjtu=True).count()', '"sjtu_members": newcomers.count()', [MONTH]),
    ("old articles count", A, "            first_published_at__gte=period.since, first_published_at__lt=period.until\n", "            first_published_at__lt=period.until\n", [MONTH]),
    ("old teams count", A, "            created_at__gte=period.since, created_at__lt=period.until\n", "            created_at__lt=period.until\n", [MONTH]),
    ("1 September belongs to the year before", A, "if (today.month, today.day) >= (month, day)", "if (today.month, today.day) > (month, day)", [PERIODS]),
    ("thirty-one days", A, "    return Period(today - timedelta(days=days - 1), today)\n", "    return Period(today - timedelta(days=days), today)\n", [PERIODS]),
    ("backwards periods pass", A, "    if start > end:\n", "    if False:\n", [PERIODS]),
    ("scrim managers shut out", A, "        or scrim_services.can_manage(user)\n", "", [OFFICERS]),
    ("no BOM", A, "    out = io.StringIO()\n    out.write(", "    out = io.StringIO()\n    (lambda _: None)(", [OFFICERS]),
    ("menu for everyone", "core/wagtail_hooks.py", "        from core.activity import can_view\n\n        return can_view(request.user)\n", "        return True\n", [WRITERS]),
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
