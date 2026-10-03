"""Round 139: break each new rule once and check its test goes red (AGENTS.md
rule 7). Runs the tests first and stops if they are not green (083).

bash scripts/remote-check.sh run uv run python handoff/rounds/139-time-changed/mutate.py
"""

import os
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
PY = sys.executable
ENV = {**os.environ, "PYTHONUTF8": "1"}

T = "tournaments/tests/test_time_changed.py"
S = "scrims/tests/test_time_changed.py"


def t(name):
    return f"{T}::{name}"


def s(name):
    return f"{S}::{name}"


MUTATIONS = [
    ("tournament admin save says nothing", "tournaments/wagtail_hooks.py",
     "        services.time_changed(instance, old_starts_at)\n", "",
     [t("test_saving_in_the_admin_sends_it")]),
    ("tournament: drafts tell people", "tournaments/services.py",
     "        tournament.status != TournamentStatus.PUBLISHED\n        or old_starts_at is None\n",
     "        old_starts_at is None\n", [t("test_nothing_said_when_nothing_moved")]),
    ("tournament: an unchanged time tells people", "tournaments/services.py",
     "        or new == old_starts_at\n        or new <= timezone.now()\n    ):\n        return False\n    Tournament.",
     "        or new <= timezone.now()\n    ):\n        return False\n    Tournament.",
     [t("test_nothing_said_when_nothing_moved")]),
    ("tournament: moving into the past tells people", "tournaments/services.py",
     "        or new == old_starts_at\n        or new <= timezone.now()\n    ):\n        return False\n    Tournament.",
     "        or new == old_starts_at\n    ):\n        return False\n    Tournament.",
     [t("test_nothing_said_when_nothing_moved")]),
    ("tournament: the old reminder still counts", "tournaments/services.py",
     "    Tournament.objects.filter(pk=tournament.pk).update(reminder_sent_at=None)\n", "",
     [t("test_the_people_taking_part_hear_from_when_to_when")]),
    ("tournament: the pool is left out", "tournaments/notifications.py",
     "    ) | set(tournament.individual_signups.values_list(\"user_id\", flat=True))\n", "    )\n",
     [t("test_the_pool_hears_too")]),
    ("tournament: rejected rosters hear", "tournaments/notifications.py",
     "        tournament.roster_members.filter(is_active=True).values_list(\n",
     "        tournament.roster_members.values_list(\n",
     [t("test_a_rejected_roster_does_not_hear")]),
    ("tournament: the old time is not said", "tournaments/notifications.py",
     "原来 {moment(old_starts_at)}，", "",
     [t("test_the_people_taking_part_hear_from_when_to_when")]),
    ("scrim admin save says nothing", "scrims/wagtail_hooks.py",
     "        services.time_changed(instance, old_starts_at)\n", "",
     [s("test_saving_in_the_admin_sends_it")]),
    ("scrim: drafts tell people", "scrims/services.py",
     "        scrim.status != ScrimStatus.PUBLISHED\n        or old_starts_at is None\n",
     "        old_starts_at is None\n", [s("test_nothing_said_when_nothing_moved")]),
    ("scrim: the old reminder still counts", "scrims/services.py",
     "    Scrim.objects.filter(pk=scrim.pk).update(reminder_sent_at=None)\n", "",
     [s("test_everyone_signed_up_hears")]),
    ("scrim: the old time is not said", "scrims/notifications.py",
     "原来 {old}，", "", [s("test_everyone_signed_up_hears")]),
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
