"""Round 059: mutate each guard the new tests are meant to catch, in place."""
import os
import pathlib
import subprocess
import sys

sys.path.insert(0, "handoff/rounds/042-guard-sweep")
import mutate_guards as m  # noqa: E402

T = {
    "teams": ["teams/tests/test_teams.py"],
    "reg": ["tournaments/tests/test_guards.py"],
    "api": ["integrations/tests/test_api_guards.py"],
    "sec": ["core/tests/test_security_guards.py"],
    "gate": ["core/tests/test_admin_gates.py"],
    "lfg": ["lfg/tests/test_lfg.py"],
    "scrims": ["scrims/tests/test_scrims.py"],
    "teaming": ["scrims/tests/test_teaming.py", "--deselect", "scrims/tests/test_teaming.py::test_6v6_finishes_within_a_second"],
    "fonts": ["core/tests/test_fonts.py"],
}
TARGETS = [
    ("teams/services.py", "update_team", "not is_captain(team, user)", "teams"),
    ("teams/services.py", "approve_application", "application.status != ApplicationStatus.PENDING", "teams"),
    ("teams/services.py", "approve_application", "already_member", "teams"),
    ("teams/services.py", "reject_application", "not is_captain", "teams"),
    ("teams/services.py", "reject_application", "application.status != ApplicationStatus.PENDING", "teams"),
    ("teams/services.py", "cancel_application", "application.applicant_id != actor.pk", "teams"),
    ("teams/services.py", "cancel_application", "application.status != ApplicationStatus.PENDING", "teams"),
    ("teams/services.py", "leave_team", "membership is None", "teams"),
    ("teams/services.py", "remove_member", "not is_captain", "teams"),
    ("teams/services.py", "remove_member", "membership is None", "teams"),
    ("teams/services.py", "transfer_captain", "not is_captain", "teams"),
    ("teams/services.py", "transfer_captain", "target.is_captain", "teams"),
    ("teams/services.py", "transfer_captain", "captained_count(new_captain)", "teams"),
    ("teams/services.py", "assign_captain", "not actor.is_superuser", "teams"),
    ("teams/forms.py", "TeamForm.clean_logo_file", "uploaded.size > LOGO_MAX_BYTES", "teams"),
    ("teams/forms.py", "TeamForm.clean_logo_file", "not name.endswith(LOGO_EXTENSIONS)", "teams"),
    ("tournaments/registration.py", "withdraw", "not is_team_captain", "reg"),
    ("tournaments/registration.py", "reject", "registration.status == RegistrationStatus.AWAITING_UPSTREAM and", "reg"),
    ("tournaments/registration.py", "member_problems", "not can_use(user", "reg"),
    ("tournaments/registration_views.py", "register", "not tournament.is_public", "reg"),
    ("tournaments/services.py", "publish", "tournament.status == TournamentStatus.CANCELLED", "reg"),
    ("integrations/api_views.py", "TournamentUpsertView.put", "review_mode not in ReviewMode.values", "api"),
    ("integrations/api_views.py", "TournamentUpsertView.put", "opens_at is None or closes_at is None", "api"),
    ("integrations/api_views.py", "TournamentUpsertView.put", "opens_at >= closes_at", "api"),
    ("integrations/api_views.py", "TournamentUpsertView.put", "not (1 <= roster_min", "api"),
    ("integrations/api_views.py", "TournamentUpsertView.put", "status_value not in TournamentStatus.values", "api"),
    ("integrations/api_views.py", "RegistrationDetailView.get", "registration is None", "api"),
    ("integrations/api_views.py", "RegistrationLogsView.get", "registration is None", "api"),
    ("integrations/api_views.py", "RegistrationReviewView.post", "registration is None", "api"),
    ("integrations/api_views.py", "TournamentRosterView.get", "tournament is None", "api"),
    ("integrations/api_views.py", "TournamentRosterCsvView.get", "tournament is None", "api"),
    ("integrations/api_views.py", "TournamentStatsView.get", "tournament is None", "api"),
    ("integrations/api_views.py", "perform_review", "roster_version is None", "api"),
    ("integrations/api_views.py", "perform_review", "upstream_review_allowed", "api"),
    ("integrations/api_views.py", "RegistrationReviewBatchView.post", "not isinstance(items, list)", "api"),
    ("integrations/api.py", "authenticate", "len(nonce)", "api"),
    ("integrations/pagination.py", "decode_cursor", "moment is None", "api"),
    ("integrations/pagination.py", "read_limit", "limit < 1", "api"),
    ("integrations/pagination.py", "apply_updated_since", "moment is None", "api"),
    ("core/net.py", "assert_public_https_url", 'parts.scheme != "https"', "sec"),
    ("core/net.py", "assert_public_https_url", 'parts.scheme not in', "sec"),
    ("core/net.py", "assert_public_https_url", "not host", "sec"),
    ("core/prerender.py", "normalize_path", 'not path.startswith("/")', "sec"),
    ("core/prerender.py", "normalize_path", '"?" in path', "sec"),
    ("core/prerender.py", "normalize_path", '".." in path', "sec"),
    ("core/prerender.py", "render_html", "response.status_code != 200", "sec"),
    ("core/prerender.py", "render_html", '"text/html" not in content_type', "sec"),
    ("sjtu_ow/settings/prod.py", "<module>", "not ALLOWED_HOSTS", "sec"),
    ("sjtu_ow/settings/prod.py", "<module>", "not CSRF_TRUSTED_ORIGINS", "sec"),
    ("sjtu_ow/settings/prod.py", "<module>", "WEBHOOK_ALLOW_INSECURE_URLS", "sec"),
    ("sjtu_ow/settings/env.py", "env", "required and default is None", "sec"),
    ("core/views.py", "send_site_test_email", "has_perm", "gate"),
    ("moderation/admin_views.py", "reviewer_required.wrapper", "can_review", "gate"),
    ("scrims/split_admin.py", "split_view", "can_manage", "gate"),
    ("scrims/split_admin.py", "copy_view", "can_manage", "gate"),
    ("scrims/wagtail_hooks.py", "manager_required.wrapper", "can_manage", "gate"),
    ("teams/wagtail_hooks.py", "superuser_required.wrapper", "is_superuser", "gate"),
    ("lfg/services.py", "create_post", "not allowed", "lfg"),
    ("lfg/services.py", "create_post", "not mode.is_active", "lfg"),
    ("lfg/services.py", "update_post", "post.status == LfgStatus.CLOSED", "lfg"),
    ("lfg/services.py", "update_post", "game_account.user_id != user.pk", "lfg"),
    ("lfg/services.py", "update_post", "not any(roles.values())", "lfg"),
    ("lfg/services.py", "set_status", "status not in LfgStatus.values", "lfg"),
    ("scrims/services.py", "cancel_scrim", "scrim.status == ScrimStatus.CANCELLED", "scrims"),
    ("scrims/views.py", "scrim_signup", "is_authenticated", "scrims"),
    ("scrims/views.py", "scrim_cancel_signup", "is_authenticated", "scrims"),
    ("scrims/views.py", "me_scrims", "is_authenticated", "scrims"),
    ("scrims/teaming.py", "check_feasible", "stuck", "teaming"),
    ("scrims/teaming.py", "generate", "not tied", "teaming"),
    ("core/fonts/processing.py", "inspect_font", "FSTYPE_BITMAP_ONLY", "fonts"),
    ("core/fonts/processing.py", "inspect_font", "not codepoints", "fonts"),
]
env = dict(os.environ, PYTHONDONTWRITEBYTECODE="1")
caught = 0
for path, function, needle, suite in TARGETS:
    matches = [g for g in m.find_guards(path) if g["function"] == function and needle in g["condition"]]
    if len(matches) != 1:
        print(f"? 定位失败 {path} {function} {needle}: {len(matches)} 处", flush=True)
        continue
    guard = matches[0]
    p = pathlib.Path(path)
    original = p.read_text()
    try:
        p.write_text(m.mutate(original, guard["span"]))
        r = subprocess.run([".venv/bin/python", "-m", "pytest", "-q", "-x", "-p", "no:cacheprovider", *T[suite]],
                           capture_output=True, text=True, env=env, timeout=900)
    finally:
        p.write_text(original)
    assert p.read_text() == original
    failed = [l.split(" - ")[0].split("::")[-1] for l in r.stdout.splitlines() if l.startswith(("FAILED", "ERROR"))]
    ok = r.returncode == 1
    caught += ok
    print(("✓ 被抓到 " if ok else "✗ 没抓到 ") + f"{path}:{guard['line']} {function}  if {guard['condition'][:60]}  ← {failed[:1]}", flush=True)
print(f"{caught}/{len(TARGETS)} 被抓到，全部还原", flush=True)
