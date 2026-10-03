"""Round 117: break each new rule once and check its test goes red (AGENTS.md
rule 7). Runs the tests first and stops if they are not green (083).

uv run python handoff/rounds/117-admin-wording/mutate.py
"""

import os
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
PY = sys.executable
ENV = {**os.environ, "PYTHONUTF8": "1"}

T = "core/tests/test_admin_wording.py"
SETTINGS = "sjtu_ow/settings/base.py"
ACCOUNT_HOOKS = "accounts/wagtail_hooks.py"


def t(name):
    return f"{T}::{name}"


MUTATIONS = [
    ("the project's translations are not loaded", SETTINGS,
     'LOCALE_PATHS = [BASE_DIR / "locale"]\n', "LOCALE_PATHS = []\n",
     [t("test_the_admin_has_no_wagtail_english_left")]),
    ("a .po edited without recompiling", "locale/zh_Hans/LC_MESSAGES/django.po",
     'msgstr "快捷键"\n', 'msgstr "快捷方式"\n',
     [t("test_the_committed_mo_files_match_the_po_files")]),
    ("the compiler drops contexts", "core/translations.py",
     '        if "msgctxt" in entry:\n            key = entry["msgctxt"] + CONTEXT_SEPARATOR + key\n', "",
     [t("test_the_compiler_writes_what_python_gettext_reads")]),
    ("the compiler keeps untranslated entries", "core/translations.py",
     "            if not value:\n                continue\n", "            if False:\n                continue\n",
     [t("test_the_compiler_writes_what_python_gettext_reads")]),
    ("the compiler output depends on order", "core/translations.py",
     '    keys = sorted(catalog, key=lambda key: key.encode("utf-8"))\n', "    keys = list(catalog)\n",
     [t("test_the_compiler_writes_what_python_gettext_reads")]),
    ("tabs say Wagtail again", "templates/wagtailadmin/admin_base.html",
     "{% block branding_title %}SJTU OW 后台{% endblock %}\n", "",
     [t("test_admin_tabs_name_the_site_not_wagtail")]),
    ("every language offered", SETTINGS,
     'WAGTAILADMIN_PERMITTED_LANGUAGES = [("zh-hans", "简体中文")]\n', "",
     [t("test_one_language_one_time_zone_and_no_upgrade_notice")]),
    ("every time zone offered", SETTINGS,
     'WAGTAIL_USER_TIME_ZONES = ["Asia/Shanghai"]\n', "",
     [t("test_one_language_one_time_zone_and_no_upgrade_notice")]),
    ("the upgrade notice is back", SETTINGS,
     "WAGTAIL_ENABLE_UPDATE_CHECK = False\n", "WAGTAIL_ENABLE_UPDATE_CHECK = True\n",
     [t("test_one_language_one_time_zone_and_no_upgrade_notice")]),
    ("the locale is Simplified Chinese again", SETTINGS,
     'WAGTAIL_CONTENT_LANGUAGES = [("zh-hans", "简体中文")]\n', "",
     [t("test_the_locale_shows_in_chinese")]),
    ("categories say True and False", "content/wagtail_hooks.py",
     '        BooleanColumn(\n            "allow_submission", label="开放投稿", sort_key="allow_submission"\n        ),\n',
     '        "allow_submission",\n',
     [t("test_yes_no_columns_are_ticks_not_true_and_false")]),
    ("member groups say True and False", "members/wagtail_hooks.py",
     '        BooleanColumn("is_visible", label="显示", sort_key="is_visible"),\n', '        "is_visible",\n',
     [t("test_yes_no_columns_are_ticks_not_true_and_false")]),
    ("user rules say True and False", ACCOUNT_HOOKS,
     '            accessor=lambda rule: "单独允许" if rule.allowed else "单独禁止",\n',
     '            accessor="allowed",\n',
     [t("test_yes_no_columns_are_ticks_not_true_and_false")]),
    ("static pages show kind codes", "core/templates/core/prerender/index.html",
     "          <td>{{ record.kind_label }}</td>", "          <td>{{ record.kind }}</td>",
     [t("test_the_static_pages_list_speaks_chinese_filters_and_pages")]),
    ("static pages ignore the status filter", "core/prerender_admin.py",
     "    if status:\n        records = records.filter(status=status)\n",
     "    if False:\n        records = records.filter(status=status)\n",
     [t("test_the_static_pages_list_speaks_chinese_filters_and_pages")]),
    ("static pages on one long page", "core/prerender_admin.py",
     "PER_PAGE = 50\n", "PER_PAGE = 500\n",
     [t("test_the_static_pages_list_speaks_chinese_filters_and_pages")]),
    ("the scrim menu says 内战", "scrims/wagtail_hooks.py",
     '        "内战活动",\n        reverse("scrims:index"),', '        "内战",\n        reverse("scrims:index"),',
     [t("test_the_menu_follows_the_design_order")]),
    ("tournaments drop down the community menu", "tournaments/wagtail_hooks.py",
     '        icon_name="date",\n        order=10,', '        icon_name="date",\n        order=100,',
     [t("test_the_menu_follows_the_design_order")]),
    ("users go back under settings", "accounts/admin_users.py",
     "class SiteUserViewSet(wagtail_users.UserViewSet):\n    menu_hook = USERS_MENU_HOOK\n",
     "class SiteUserViewSet(wagtail_users.UserViewSet):\n",
     [t("test_the_menu_follows_the_design_order")]),
    ("groups are called 组", "accounts/admin_users.py",
     '    menu_label = "用户组"\n', "",
     [t("test_the_menu_follows_the_design_order")]),
    ("feature permissions go back under settings", ACCOUNT_HOOKS,
     "    menu_order = 700\n    menu_hook = USERS_MENU_HOOK\n",
     "    menu_order = 700\n    add_to_settings_menu = True\n",
     [t("test_the_menu_follows_the_design_order")]),
    ("the users menu after reports", ACCOUNT_HOOKS,
     "        order=8000,\n", "        order=9500,\n",
     [t("test_the_menu_follows_the_design_order")]),
    ("reports and help for everyone", ACCOUNT_HOOKS,
     "    if user.is_superuser or user.groups.filter(name=GROUP_CONTENT).exists():\n        return\n",
     "    return\n",
     [t("test_reports_and_help_are_for_superusers_and_content_editors")]),
    ("only pure submitters are filtered in the tree", "content/wagtail_hooks.py",
     "    if not sees_only_own_drafts(request.user):\n        return pages",
     "    if not is_submitter_only(request.user):\n        return pages",
     [t("test_both_page_tree_filters_hide_others_drafts")]),
    ("only pure submitters are filtered in explorable pages", "content/wagtail_hooks.py",
     "    pages = _original_explorable_instances(self, user)\n    if sees_only_own_drafts(user):",
     "    pages = _original_explorable_instances(self, user)\n    if is_submitter_only(user):",
     [t("test_both_page_tree_filters_hide_others_drafts")]),
    ("both tree filters miss tournament managers", "content/permissions.py",
     "    return GROUP_CONTENT not in _group_names(user)\n",
     "    return is_submitter_only(user)\n",
     [t("test_staff_who_are_also_submitters_do_not_see_others_drafts")]),
    ("a stock workflow with approvers is retired too", "content/services.py",
     '            getattr(task, "groups", None) and task.groups.exists() for task in tasks\n',
     "            False for task in tasks\n",
     [t("test_a_stock_workflow_with_approvers_is_left_alone")]),
    ("init_site leaves the stock workflow on", "core/management/commands/init_site.py",
     "        if retire_wagtail_stock_workflow():\n", "        if False and retire_wagtail_stock_workflow():\n",
     [t("test_init_site_retires_the_workflow_nobody_can_approve")]),
    ("the migration keeps 「Root」", "content/migrations/0006_retire_stock_workflow.py",
     '    Page.objects.filter(depth=1, title="Root").update(\n',
     '    Page.objects.filter(depth=1, title="Nothing").update(\n',
     [t("test_the_migration_retires_it_on_existing_sites")]),
    ("the migration retires workflows with approvers", "content/migrations/0006_retire_stock_workflow.py",
     "            pk__in=task_ids, groups__isnull=False\n        ).exists():\n",
     "            pk__in=task_ids, groups__isnull=False\n        ).exists() and False:\n",
     [t("test_the_migration_retires_it_on_existing_sites")]),
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
