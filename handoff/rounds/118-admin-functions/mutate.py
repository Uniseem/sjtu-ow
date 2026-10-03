"""Round 118: break each new rule once and check its test goes red (AGENTS.md
rule 7). Runs the tests first and stops if they are not green (083).

uv run python handoff/rounds/118-admin-functions/mutate.py
"""

import os
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
PY = sys.executable
ENV = {**os.environ, "PYTHONUTF8": "1"}

T = "core/tests/test_admin_functions.py"
TODO = "core/admin_todo.py"
SPLIT = "scrims/templates/scrims/admin/split.html"


def t(name):
    return f"{T}::{name}"


MUTATIONS = [
    ("the dashboard has no to-do panel", "core/wagtail_hooks.py",
     "        panels.insert(0, TodoPanel())\n", "        pass\n",
     [t("test_content_editors_see_what_waits_for_review")]),
    ("reviewers get no review rows", TODO,
     "    if not can_review(user):\n        return []\n", "    if True:\n        return []\n",
     [t("test_content_editors_see_what_waits_for_review")]),
    ("avatars counted by the wrong status", TODO,
     "        status=AvatarSubmission.Status.PENDING\n", "        status=AvatarSubmission.Status.APPROVED\n",
     [t("test_content_editors_see_what_waits_for_review")]),
    ("submissions counted for nobody", TODO,
     "        tasks = GroupApprovalTask.objects.filter(groups__in=user.groups.all())\n",
     "        tasks = GroupApprovalTask.objects.none()\n",
     [t("test_editors_see_submissions_waiting_for_them")]),
    ("tournament managers get no rows", TODO,
     "    if not tournament_services.can_manage(user):\n        return []\n",
     "    if True:\n        return []\n",
     [t("test_tournament_managers_see_registrations_and_the_pool")]),
    ("the pool counts placed people", TODO,
     "            registration__isnull=True, tournament__status=TournamentStatus.PUBLISHED\n",
     "            registration__isnull=False, tournament__status=TournamentStatus.PUBLISHED\n",
     [t("test_tournament_managers_see_registrations_and_the_pool")]),
    ("split scrims stay on the list", TODO,
     '        .exclude(signups__team__in=["a", "b"])\n', "",
     [t("test_scrim_managers_see_closed_scrims_without_teams")]),
    ("superusers miss failed pages", TODO,
     "    if not user.is_superuser:\n        return []\n    failed",
     "    if True:\n        return []\n    failed",
     [t("test_superusers_see_failed_static_pages")]),
    ("empty rows are listed", TODO,
     "    return [row for row in rows if row.count]\n", "    return rows\n",
     [t("test_nothing_waiting_says_so_and_people_without_queues_get_no_panel")]),
    ("everyone gets the panel", TODO,
     "def has_duties(user) -> bool:\n", "def has_duties(user) -> bool:\n    return True\n",
     [t("test_nothing_waiting_says_so_and_people_without_queues_get_no_panel")]),
    ("the review list ignores the time filter", "moderation/admin_views.py",
     "    if since:\n", "    if False:\n",
     [t("test_the_review_list_filters_by_time")]),
    ("two scans at once", "moderation/admin_views.py",
     "    elif not cache.add(SCAN_LOCK_KEY, request.user.pk, wait + SCAN_LOCK_SECONDS):\n",
     "    elif False:\n",
     [t("test_the_full_scan_runs_in_the_background_once_at_a_time")]),
    ("the scan runs at peak prices", "moderation/tasks.py",
     "    if OFF_PEAK_START <= local.time() < OFF_PEAK_END:\n", "    if True:\n",
     [t("test_the_full_scan_waits_for_the_off_peak_hours")]),
    ("the scan keeps its lock", "moderation/tasks.py",
     "        cache.delete(SCAN_LOCK_KEY)\n", "        pass\n",
     [t("test_the_scan_task_releases_its_lock")]),
    ("the scan skips teams", "moderation/integrations.py",
     "            submitted += submit_team(team)\n", "            pass\n",
     [t("test_the_scan_covers_teams_and_comments_too")]),
    ("the scan skips comments", "moderation/integrations.py",
     "            if submit_comment(comment) is not None:\n", "            if False:\n",
     [t("test_the_scan_covers_teams_and_comments_too")]),
    ("handling is not logged", "moderation/admin_views.py",
     "    wagtail_log(\n        instance=item,\n", "    (lambda **kwargs: None)(\n        instance=item,\n",
     [t("test_every_handling_stays_on_record")]),
    ("saving drops the order", "scrims/split_admin.py",
     '        order = _order(request.POST.get("order"))\n', '        order = "created"\n',
     [t("test_the_split_page_keeps_its_order_after_saving")]),
    ("the current order is not marked", SPLIT,
     '{% if order == value %} aria-current="true"{% endif %}', "",
     [t("test_the_split_page_keeps_its_order_after_saving")]),
    ("managers see no contacts", "scrims/split_admin.py",
     "    if not can_see_contacts(request.user):\n", "    if True:\n",
     [t("test_scrim_managers_see_contacts_on_the_split_page")]),
    ("everyone sees contacts", "scrims/split_admin.py",
     "    if not can_see_contacts(request.user):\n", "    if False:\n",
     [t("test_scrim_managers_see_contacts_on_the_split_page")]),
    ("no copy button", SPLIT,
     '<button type="button" class="button button-secondary" data-copy-button>复制</button>', "",
     [t("test_the_split_result_has_a_copy_button")]),
    ("the copy button copies nothing", "static/js/scrim-split.js",
     "        navigator.clipboard.writeText(text.value).then(\n", "        Promise.resolve(text.value).then(\n",
     [t("test_the_split_result_has_a_copy_button")]),
    ("the split table hides deactivation", SPLIT,
     "{{ signup.user.nickname }}{% if not signup.user.is_active %}（账号已停用）{% endif %}</td>",
     "{{ signup.user.nickname }}</td>",
     [t("test_split_page_marks_deactivated_accounts")]),
    ("split cards hide deactivation", "scrims/templates/scrims/admin/_card.html",
     "{% if not signup.user.is_active %}（账号已停用）{% endif %}", "",
     [t("test_split_page_marks_deactivated_accounts")]),
    ("the review list hides deactivation", "tournaments/templates/tournaments/admin/review_index.html",
     "{% if registration.deactivated %}", "{% if False %}",
     [t("test_registration_review_marks_deactivated_accounts")]),
    ("the review list counts nobody", "tournaments/review_admin.py",
     "                filter=Q(members__is_active=True, members__user__is_active=False),\n",
     "                filter=Q(pk__in=[]),\n",
     [t("test_registration_review_marks_deactivated_accounts")]),
    ("the roster hides deactivation", "tournaments/templates/tournaments/admin/review_detail.html",
     "{% if not row.member.user.is_active %}（账号已停用）{% endif %}", "",
     [t("test_registration_review_marks_deactivated_accounts")]),
    ("the board hides deactivation", "tournaments/templates/tournaments/admin/_card.html",
     "{% if not entry.user.is_active %}（账号已停用）{% endif %}", "",
     [t("test_the_arrangement_board_marks_deactivated_accounts")]),
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
