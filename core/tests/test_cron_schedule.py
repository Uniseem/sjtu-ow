"""Cron runs on Beijing time whatever the server's clock does (218, 09-9).

The formal site's server is on Europe/Berlin. Debian's cron has no CRON_TZ, and
a Beijing hour converted into the server's hours and written down is an hour out
for half of every year. The crontab now fires every hour and
``deploy/at-shanghai.sh`` decides, on Beijing time, whether it is the hour.
"""

import re
import subprocess
from datetime import UTC, datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "deploy" / "at-shanghai.sh"
CRONTAB = ROOT / "deploy" / "crontab.example"
BEIJING = ZoneInfo("Asia/Shanghai")
BERLIN = ZoneInfo("Europe/Berlin")


def _runs(epoch, *args):
    done = subprocess.run(
        ["sh", str(SCRIPT), *args, "--", "echo", "ran"],
        env={"PATH": "/usr/bin:/bin", "AT_SHANGHAI_EPOCH": str(int(epoch))},
        capture_output=True,
        text=True,
    )
    assert done.returncode == 0, done.stderr
    return done.stdout.strip() == "ran"


def _epoch(*when, tz=BEIJING):
    return datetime(*when, tzinfo=tz).timestamp()


def test_it_runs_in_the_beijing_hour_and_not_in_any_other():
    for hour in range(24):
        assert _runs(_epoch(2026, 10, 7, hour, 0), "3") is (hour == 3)
        assert _runs(_epoch(2026, 10, 7, hour, 59), "4") is (hour == 4)


def test_the_weekday_is_the_weekday_in_beijing():
    sunday = _epoch(2026, 10, 25, 4, 30)  # a Sunday in Beijing
    assert datetime.fromtimestamp(sunday, BEIJING).weekday() == 6
    assert _runs(sunday, "4", "0")
    assert not _runs(sunday + 86400, "4", "0")
    for later in range(1, 7):
        assert not _runs(sunday + later * 86400, "4", "0")
    # 21:30 on the Saturday in Berlin is already Sunday 04:30 in Beijing
    berlin = datetime.fromtimestamp(sunday, BERLIN)
    assert berlin.weekday() == 5 and berlin.hour in (21, 22)


def test_the_hour_does_not_drift_when_berlin_changes_its_clocks():
    """Tick every real hour (what ``0 * * * *`` does) over the days around the
    switch back to winter time, 2026-10-25: the run lands on 03:00 Beijing
    time once a day, before and after, which the old fixed hour did not."""
    start = datetime(2026, 10, 22, 0, 0, tzinfo=UTC)
    fired = []
    for tick in range(24 * 7):
        moment = start + timedelta(hours=tick)
        if _runs(moment.timestamp(), "3"):
            fired.append(moment)
    assert [m.astimezone(BEIJING).strftime("%m-%d %H:%M") for m in fired] == [
        f"10-{day} 03:00" for day in range(23, 30)
    ]
    # the Berlin hour it fell on really did change
    assert {m.astimezone(BERLIN).hour for m in fired} == {20, 21}


def test_a_nonsense_call_is_refused_and_runs_nothing():
    for args in (["25", "--", "echo", "ran"], ["3", "7", "--", "echo", "ran"], ["3"]):
        done = subprocess.run(
            ["sh", str(SCRIPT), *args],
            env={"PATH": "/usr/bin:/bin", "AT_SHANGHAI_EPOCH": "0"},
            capture_output=True,
            text=True,
        )
        assert done.returncode == 64 and "ran" not in done.stdout


def test_the_exit_code_of_the_command_is_kept():
    done = subprocess.run(
        ["sh", str(SCRIPT), "3", "--", "sh", "-c", "exit 7"],
        env={
            "PATH": "/usr/bin:/bin",
            "AT_SHANGHAI_EPOCH": str(int(_epoch(2026, 10, 7, 3, 0))),
        },
    )
    assert done.returncode == 7


# --- the crontab matches the schedule in design 16.5 ------------------------------

DESIGN_16_5 = {
    # (minute, hour, weekday or None): the manage.py command
    (0, 3, None): "backup",
    (0, 4, None): "cleanup_old_data",
    (15, 4, None): "prerender",
    (20, 4, None): "cleanup_static",
    (30, 4, 0): "optimize_db",
}

ENTRY = re.compile(
    r"^(?P<minute>\d+) \* \* \* \* \$AT (?P<hour>\d+)(?: (?P<weekday>\d))? -- "
    r"\$DC exec -T web python manage\.py (?P<command>\w+)$"
)


def _entries():
    lines = CRONTAB.read_text(encoding="utf-8").splitlines()
    return [
        line
        for line in lines
        if line.strip() and not line.startswith("#") and not re.match(r"^[A-Z]+=", line)
    ]


def test_every_crontab_entry_goes_through_the_wrapper_and_matches_the_design():
    found = {}
    for line in _entries():
        match = ENTRY.match(line)
        assert match, f"not in the form 「每小时一次 + at-shanghai」: {line}"
        weekday = match["weekday"]
        found[
            (
                int(match["minute"]),
                int(match["hour"]),
                None if weekday is None else int(weekday),
            )
        ] = match["command"]
    assert found == DESIGN_16_5


def test_the_crontab_no_longer_leans_on_the_servers_clock():
    text = CRONTAB.read_text(encoding="utf-8")
    assert "CRON_TZ=" not in text
    assert re.search(r"^AT=sh /srv/sjtu-ow/deploy/at-shanghai\.sh$", text, re.M)
    assert SCRIPT.is_file()
