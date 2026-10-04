"""Round 179: the guards the sweep found untested, each broken once (condition
replaced by False) to check the test added for it goes red (AGENTS.md rule 7).
Runs the tests first and stops if they are not green (083).

bash scripts/remote-check.sh run uv run python handoff/rounds/179-guard-sweep/mutate.py
"""

import os
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
PY = sys.executable
ENV = {**os.environ, "PYTHONUTF8": "1"}

G = "accounts/tests/test_guards_left_open.py::"
EMAIL = G + "test_accounts_need_an_email_and_superusers_both_flags"
SCORE = G + "test_scores_outside_the_table_are_refused"
VANISHED = G + "test_a_picture_that_vanished_cannot_be_approved"
FACE = G + "test_only_the_face_in_use_can_be_taken_down"
UNDO = "comments/tests/test_comment_extras.py::test_readers_cannot_undo_what_editors_did"
LEGAL = "content/tests/test_legal_pages.py::test_the_command_asks_for_init_site_first"
NOSITE = "content/tests/test_submissions.py::test_site_hostname_sync_says_when_there_is_no_site"
FONT = "core/tests/test_fonts.py::test_an_oversized_upload_is_refused_before_it_is_read"
PROBE = "core/tests/test_pages.py::test_a_write_that_does_not_show_up_fails_the_check"
SMTP = "core/tests/test_mail.py::test_a_test_email_the_server_did_not_take_is_an_error"
CLASH = "core/tests/test_ops_commands.py::test_a_second_backup_in_the_same_second_does_not_overwrite"
NODB = "core/tests/test_ops_commands.py::test_an_archive_without_a_database_is_refused"
S = "core/tests/test_security_guards.py::"
INSIDE = S + "test_addresses_inside_our_network_are_refused"
RESOLVED = S + "test_a_name_that_resolves_inside_is_refused_too"
REDIRECT = S + "test_a_redirect_into_our_network_is_refused"
OFF = "core/tests/test_offsite_backup.py::test_upload_itself_refuses_when_the_feature_is_off"
MISSING = "core/tests/test_offsite_backup.py::test_listing_pruning_and_fetching_say_what_is_missing"
PO = "core/tests/test_admin_wording.py::test_a_broken_po_file_is_refused_not_half_read"
RESCUE = "teams/tests/test_teams.py::test_superuser_can_assign_a_captain"
NOGAMEID = "tournaments/tests/test_registration.py::test_check_7_a_member_who_removed_every_game_id"
TR = "core/translations.py"
A = "tournaments/tests/test_adhoc_teams.py::"
STALE = A + "test_saving_a_board_that_names_a_dissolved_team"
GONE = A + "test_nobody_leaves_a_team_that_was_already_dissolved"
SHORT = A + "test_the_board_flags_a_team_that_fell_below_the_minimum"
REG = "tournaments/registration.py"

AM = "accounts/models.py"
AS = "accounts/services.py"
CS = "comments/services.py"
FF = "core/fonts/forms.py"

MUTATIONS = [
    ("no email accepted", AM, "        if not email:\n", "        if False:\n", [EMAIL]),
    ("superuser without is_staff", AM, '        if extra_fields.get("is_staff") is not True:\n', "        if False:\n", [EMAIL]),
    ("superuser without is_superuser", AM, '        if extra_fields.get("is_superuser") is not True:\n', "        if False:\n", [EMAIL]),
    ("any score decoded", "accounts/ranks.py", "    if not isinstance(score, int) or score < 0 or score > 39:\n", "    if False:\n", [SCORE]),
    ("vanished picture approved", AS, "        if submission.image_id is None:\n", "        if False:\n", [VANISHED]),
    ("old face taken down", AS, "        if not submission.image_id or user.avatar_id != submission.image_id:\n", "        if False:\n", [FACE]),
    ("readers unhide", CS, '''def unhide(*, comment, actor) -> Comment:
    if not can_moderate(actor):''', '''def unhide(*, comment, actor) -> Comment:
    if False:''', [UNDO]),
    ("readers unpin", CS, '''def unpin(*, comment, actor) -> Comment:
    if not can_moderate(actor):''', '''def unpin(*, comment, actor) -> Comment:
    if False:''', [UNDO]),
    ("legal pages without init_site", "content/management/commands/load_legal_pages.py", "            if page is None:\n", "            if False:\n", [LEGAL]),
    ("no default site", "content/services.py", '''    if site is None:
        raise Site.DoesNotExist''', '''    if False:
        raise Site.DoesNotExist''', [NOSITE]),
    ("big upload read", FF, '''        uploaded = self.cleaned_data["file"]
        if uploaded.size > processing.MAX_FONT_BYTES:''', '''        uploaded = self.cleaned_data["file"]
        if False:''', [FONT]),
    ("big weight read", FF, '''            return uploaded
        if uploaded.size > processing.MAX_FONT_BYTES:''', '''            return uploaded
        if False:''', [FONT]),
    ("probe not read back", "core/health.py", '            if not HealthProbe.objects.filter(token="__healthz__").exists():\n', "            if False:\n", [PROBE]),
    ("unsent test email", "core/mail.py", "    if not sent:\n        raise RuntimeError", "    if False:\n        raise RuntimeError", [SMTP]),
    ("backup overwritten", "core/management/commands/backup.py", "        if archive.exists():\n", "        if False:\n", [CLASH]),
    ("restore without a database", "core/management/commands/restore.py", "            if not snapshot.exists():\n", "            if False:\n", [NODB]),
    ("internal address fetched", "core/net.py", "        if is_internal(address):\n", "        if False:\n", [INSIDE, RESOLVED]),
    ("upload while off", "core/offsite.py", "    if not config.enabled:\n        raise OffsiteError", "    if False:\n        raise OffsiteError", [OFF]),
    ("listing half configured", "core/offsite.py", '''    """Recent objects under the prefix, newest first."""
    config = config or load_config()
    if config.missing:''', '''    """Recent objects under the prefix, newest first."""
    config = config or load_config()
    if False:''', [MISSING]),
    ("pruning half configured", "core/offsite.py", '''    config = config or load_config()
    if config.missing:
        raise OffsiteError(f"异地备份还缺这些设置：{'、'.join(config.missing)}")
    cutoff''', '''    config = config or load_config()
    if False:
        raise OffsiteError(f"异地备份还缺这些设置：{'、'.join(config.missing)}")
    cutoff''', [MISSING]),
    ("fetching half configured", "core/offsite.py", '''    """Fetch one object and decrypt it to ``target``."""
    config = config or load_config()
    if config.missing:''', '''    """Fetch one object and decrypt it to ``target``."""
    config = config or load_config()
    if False:''', [MISSING]),
    ("orphan .po line", TR, "            if keyword is None:\n", "            if False:\n", [PO]),
    ("doubled .po keyword", TR, "        if keyword in entry:\n", "        if False:\n", [PO]),
    ("entry without msgid", TR, "        if msgid is None:\n", "        if False:\n", [PO]),
    ("stopped account made captain", "teams/services.py", "    if not new_captain.is_active:\n", "    if False:\n", [RESCUE]),
    ("member without a game ID registered", "tournaments/registration.py", '''        if account is None:
            problems.append(f"{user.nickname} 还没有填写游戏 ID")''', '''        if False:
            problems.append(f"{user.nickname} 还没有填写游戏 ID")''', [NOGAMEID]),
    ("stale board crashes", REG, '''            if registration is None:
                problems.append("有一支队伍已经不存在了''', '''            if False:
                problems.append("有一支队伍已经不存在了''', [STALE]),
    ("leaving a dissolved team", REG, '''不能单独退出")
    if registration.status not in ACTIVE_STATUSES:''', '''不能单独退出")
    if False:''', [GONE]),
    ("short team not flagged", "tournaments/teams_admin.py", "        if len(members) < tournament.roster_min:\n", "        if False:\n", [SHORT]),
    # Not an ``if``, so the sweep never saw it; same SSRF line as core/net.py.
    ("redirects followed anywhere", "core/fonts/download.py", "        _assert_public_url(newurl)\n", "", [REDIRECT]),
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
