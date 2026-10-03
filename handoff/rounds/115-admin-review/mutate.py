"""Round 115: break each new rule once and check its test goes red (AGENTS.md
rule 7). Runs the tests first and stops if they are not green (083).

uv run python handoff/rounds/115-admin-review/mutate.py
"""

import os
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
PY = sys.executable
ENV = {**os.environ, "PYTHONUTF8": "1"}

T = "core/tests/test_admin_safety.py"


def t(name):
    return f"{T}::{name}"


MUTATIONS = [
    ("published tournaments can be deleted", "tournaments/wagtail_hooks.py",
     "        if not services.can_delete(self.object):\n            messages.error(request, \"发布过的赛事不能删除，只能取消。\")\n",
     "        if False:\n            messages.error(request, \"发布过的赛事不能删除，只能取消。\")\n",
     [t("test_a_published_tournament_cannot_be_deleted")]),
    ("the listing offers delete for published ones", "tournaments/wagtail_hooks.py",
     "        # The listing asks only the model-level permission (round 115).\n        if not services.can_delete(instance):\n",
     "        # The listing asks only the model-level permission (round 115).\n        if False:\n",
     [t("test_a_published_tournament_cannot_be_deleted")]),
    ("scrims with signups can be deleted", "scrims/services.py",
     "    return scrim.status == ScrimStatus.DRAFT and not scrim.signups.exists()\n",
     "    return True\n",
     [t("test_a_scrim_with_signups_cannot_be_deleted")]),
    ("an unknown action crashes", "tournaments/wagtail_hooks.py",
     "    if action not in ACTIONS:\n        raise Http404(\"没有这个操作。\")\n", "",
     [t("test_an_unknown_action_is_not_found")]),
    ("members change their email in the admin", "sjtu_ow/settings/base.py",
     "WAGTAIL_EMAIL_MANAGEMENT_ENABLED = False\n", "",
     [t("test_members_cannot_change_their_login_email_in_the_admin")]),
    ("the admin asks for first and last name", "accounts/wagtail_hooks.py",
     "wagtail_account.NameEmailSettingsPanel.is_active = lambda self: False\n", "",
     [t("test_members_cannot_change_their_login_email_in_the_admin")]),
    ("the admin takes an unreviewed face", "accounts/wagtail_hooks.py",
     "wagtail_account.AvatarSettingsPanel.is_active = lambda self: False\n", "",
     [t("test_members_cannot_change_their_login_email_in_the_admin")]),
    ("Wagtail's own user screens", "sjtu_ow/settings/base.py",
     '    "accounts.users_app.SiteUsersAppConfig",  # wagtail.users, site screens\n',
     '    "wagtail.users",\n',
     [t("test_the_user_page_has_the_sites_fields_not_first_and_last_name")]),
    ("stopping needs no reason", "accounts/admin_users.py",
     "        if stopping and not (cleaned.get(\"deactivation_note\") or \"\").strip():\n",
     "        if False:\n",
     [t("test_stopping_an_account_needs_a_reason_and_cancels_its_applications")]),
    ("stopping leaves applications pending", "accounts/admin_users.py",
     "            after_deactivation(instance)\n", "",
     [t("test_stopping_an_account_needs_a_reason_and_cancels_its_applications")]),
    ("users can be added in the admin", "accounts/admin_users.py",
     "class UserCreateView(wagtail_users.CreateView):\n    def dispatch(self, request, *args, **kwargs):\n        raise PermissionDenied",
     "class UserCreateView(wagtail_users.CreateView):\n    def _gone(self, request, *args, **kwargs):\n        raise PermissionDenied",
     [t("test_users_are_not_added_or_deleted_in_the_admin")]),
    ("no page links on the review list", "tournaments/templates/tournaments/admin/review_index.html",
     '      {% if registrations.has_next %}<a href="?page={{ registrations.next_page_number }}&amp;status={{ status }}&amp;tournament={{ tournament_id }}">下一页</a>{% endif %}\n',
     "",
     [t("test_the_review_list_links_to_its_other_pages")]),
    ("bulk approve follows any address", "tournaments/review_admin.py",
     "    if not url_has_allowed_host_and_scheme(back, allowed_hosts={request.get_host()}):\n        back = reverse(\"registration_review_index\")\n",
     "    if not back:\n        back = reverse(\"registration_review_index\")\n",
     [t("test_bulk_approve_stays_on_the_site")]),
    ("ad-hoc teams can be rejected here", "tournaments/registration.py",
     "    if registration.team_id is None:\n        raise RegistrationError(\"临时队伍请在「队伍编排」里调整，这里不能驳回。\")\n", "",
     [t("test_an_adhoc_team_is_not_rejected_from_the_review_page")]),
    ("the backup secret is shown", "core/forms.py",
     "    backup_s3_secret_access_key = _secret_field(\n        *SECRET_FIELDS[\"backup_s3_secret_access_key\"]\n    )\n", "",
     [t("test_the_backup_secret_is_never_shown_and_blank_keeps_it")]),
    ("a mistake replaces the contact list", "templates/me/contacts.html",
     '      {% else %}\n        hx-target="#create-contact"\n        hx-swap="innerHTML"\n',
     '      {% else %}\n        hx-target="#contact-list"\n        hx-swap="outerHTML"\n',
     [t("test_a_mistake_in_the_new_contact_form_keeps_the_list")]),
    ("a new contact does not refresh the list", "accounts/views.py",
     '                    return _whole_list(_contacts_list_response(request), "contact-list")\n',
     "                    return _contacts_list_response(request)\n",
     [t("test_a_mistake_in_the_new_contact_form_keeps_the_list")]),
    ("cancel puts the page in the list", "accounts/views.py",
     "    if request.htmx:  # 取消: back to the list, never the whole page inside it\n        return _contacts_list_response(request)\n", "",
     [t("test_cancel_brings_back_the_list_not_the_whole_page")]),
    ("deleting an old tournament's game ID crashes", "tournaments/models.py",
     "        verbose_name=\"游戏 ID\",\n        null=True,\n        blank=True,\n        on_delete=models.SET_NULL,\n        related_name=\"individual_signups\",\n",
     "        verbose_name=\"游戏 ID\",\n        null=True,\n        blank=True,\n        on_delete=models.PROTECT,\n        related_name=\"individual_signups\",\n",
     [t("test_a_game_id_from_a_finished_tournament_can_be_deleted")]),
    ("teams can be deleted in the admin", "teams/wagtail_hooks.py",
     '        if action in ("add", "delete"):\n            return False\n        return bool(getattr(user, "is_superuser", False))\n',
     '        return bool(getattr(user, "is_superuser", False))\n',
     [t("test_teams_are_not_added_or_deleted_in_the_admin")]),
    ("captains go to disbanded teams", "teams/services.py",
     "    if team.is_disbanded:  # round 115\n", "    if False:\n",
     [t("test_a_captain_is_not_assigned_to_a_disbanded_or_full_team")]),
    ("captains overfill a team", "teams/services.py",
     "        if is_full(team):\n            raise TeamError(\"战队人数已满，先移除一名成员，或者从现有成员里指定。\")\n", "",
     [t("test_a_captain_is_not_assigned_to_a_disbanded_or_full_team")]),
    ("admin team edits regenerate nothing", "teams/wagtail_hooks.py",
     "        services.on_team_changed(instance, author=self.request.user)\n", "",
     [t("test_an_admin_edit_of_a_team_regenerates_its_pages")]),
    ("comments can be deleted in the admin", "comments/wagtail_hooks.py",
     "    def user_has_permission(self, user, action):\n        if action in (\"add\", \"delete\"):\n            return False\n",
     "    def user_has_permission(self, user, action):\n",
     [t("test_comments_are_hidden_or_pinned_not_added_or_deleted")]),
    ("the comment edit page hides the comment", "comments/wagtail_hooks.py",
     '        FieldPanel("body", read_only=True),\n', "",
     [t("test_comments_are_hidden_or_pinned_not_added_or_deleted")]),
    ("disbanding asks nothing", "teams/templates/teams/manage.html",
     ' data-confirm="确定解散战队？解散后不能恢复，全体成员会收到邮件。"', "",
     [t("test_forms_that_take_something_away_ask_first")]),
    ("the script ignores the question", "static/js/app.js",
     "    if (question && !window.confirm(question)) {\n", "    if (false) {\n",
     [t("test_the_site_script_asks_the_forms_question")]),
    ("clearing static files asks nothing", "core/templates/core/prerender/index.html",
     ' onsubmit="return window.confirm(\'清空全部静态文件？清空后所有页面临时由 Django 实时渲染，直到重新生成。\')"', "",
     [t("test_admin_forms_that_take_something_away_ask_first")]),
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
