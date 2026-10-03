"""Round 119: break each new rule once and check its test goes red (AGENTS.md
rule 7). Runs the tests first and stops if they are not green (083).

uv run python handoff/rounds/119-admin-leftovers/mutate.py
"""

import os
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
PY = sys.executable
ENV = {**os.environ, "PYTHONUTF8": "1"}

T = "core/tests/test_admin_leftovers.py"


def t(name):
    return f"{T}::{name}"


MUTATIONS = [
    ("publishing a tournament is not logged", "tournaments/wagtail_hooks.py",
     "            admin_log.record(tournament, LOG_ACTIONS[action], request.user)\n", "",
     [t("test_tournament_buttons_are_on_record")]),
    ("cancelling a tournament is not logged", "tournaments/wagtail_hooks.py",
     '                tournament, "tournaments.cancel", request.user, reason=reason\n',
     '                tournament, "tournaments.cancel", request.user\n',
     [t("test_tournament_buttons_are_on_record")]),
    ("the log actions have no labels", "core/wagtail_hooks.py",
     "    for action, (label, message) in ACTIONS.items():\n", "    for action, (label, message) in {}.items():\n",
     [t("test_tournament_buttons_are_on_record")]),
    ("publishing a scrim is not logged", "scrims/wagtail_hooks.py",
     "            admin_log.record(scrim, LOG_ACTIONS[action], request.user)\n", "",
     [t("test_scrim_buttons_and_the_split_page_are_on_record")]),
    ("cancelling a scrim is not logged", "scrims/wagtail_hooks.py",
     '            admin_log.record(scrim, "scrims.cancel", request.user)\n', "",
     [t("test_scrim_buttons_and_the_split_page_are_on_record")]),
    ("saving who plays is not logged", "scrims/split_admin.py",
     '            admin_log.record(scrim, "scrims.select", request.user)\n', "",
     [t("test_scrim_buttons_and_the_split_page_are_on_record")]),
    ("saving the split is not logged", "scrims/split_admin.py",
     '            admin_log.record(scrim, "scrims.save_teams", request.user)\n', "",
     [t("test_scrim_buttons_and_the_split_page_are_on_record")]),
    ("assigning a captain is not logged", "teams/wagtail_hooks.py",
     "                captain=user.nickname,\n", "",
     [t("test_team_rescue_actions_are_on_record")]),
    ("disbanding is not logged", "teams/wagtail_hooks.py",
     '            admin_log.record(team, "teams.disband", request.user)\n', "",
     [t("test_team_rescue_actions_are_on_record")]),
    ("saving the board is not logged", "tournaments/teams_admin.py",
     '                    "tournaments.arrange",\n', '                    "tournaments.nothing",\n',
     [t("test_saving_the_arrangement_board_is_on_record")]),
    ("the editor shows no AI read", "content/models.py",
     '        ModerationVerdictPanel(heading="AI 审核"),\n', "",
     [t("test_editors_see_the_ai_read_on_a_submission")]),
    ("submitters see the AI read", "moderation/panels.py",
     "            if self.instance is not None and can_review(self.request.user):\n",
     "            if self.instance is not None:\n",
     [t("test_editors_see_the_ai_read_on_a_submission")]),
    ("an unfinished review shows as a verdict", "moderation/templates/moderation/verdict_panel.html",
     "{% if verdict.checked_at %}", "{% if True %}",
     [t("test_a_submission_still_under_review_says_so")]),
    ("the preview goes back under the form", "core/templates/core/fonts/typography.html",
     '  <div class="typography-layout">\n', "  <div>\n",
     [t("test_the_typography_preview_sits_beside_the_form")]),
    ("the preview scrolls away", "static/css/typography-admin.css",
     "    position: sticky;\n", "",
     [t("test_the_typography_preview_sits_beside_the_form")]),
    ("the minimum is only checked after saving", "tournaments/wagtail_hooks.py",
     "                self.add_error(\"roster_min\", warning)\n", "                pass\n",
     [t("test_a_team_minimum_above_the_site_cap_is_refused_before_saving")]),
    ("the field does not say the cap", "tournaments/wagtail_hooks.py",
     '                f"整队报名时不能超过全站战队人数上限（现在是 {cap} 人，"\n',
     '                "整队报名时不能超过全站战队人数上限（"\n',
     [t("test_a_team_minimum_above_the_site_cap_is_refused_before_saving")]),
    ("individual tournaments are capped too", "tournaments/services.py",
     '    if tournament.registration_mode != "team":\n        return ""\n', "",
     [t("test_a_team_minimum_above_the_site_cap_is_refused_before_saving")]),
    ("user rules query per row", "accounts/wagtail_hooks.py",
     '        qs = super().get_base_queryset().select_related("user", "updated_by")\n',
     "        qs = super().get_base_queryset()\n",
     [t("test_feature_rule_lists_do_not_query_per_row")]),
    ("group rules query per row", "accounts/wagtail_hooks.py",
     '        return super().get_base_queryset().select_related("group", "updated_by")\n',
     "        return super().get_base_queryset()\n",
     [t("test_feature_rule_lists_do_not_query_per_row")]),
    ("the board asks once per person", "tournaments/teams_admin.py",
     "        entry.conflict = conflicts[entry.pk]\n",
     "        entry.conflict = registration_service.pool_entry_conflict(entry)\n",
     [t("test_the_arrangement_board_does_not_query_per_person")]),
    ("my submissions query per article", "content/wagtail_hooks.py",
     "            .prefetch_workflow_states()\n", "",
     [t("test_my_submissions_do_not_query_per_article")]),
    ("page links drop the filters", "core/templates/core/admin/_pager.html",
     '<a href="{% querystring page=page.next_page_number %}">下一页</a>',
     '<a href="?page={{ page.next_page_number }}">下一页</a>',
     [t("test_page_links_keep_the_filters")]),
    ("the review list writes its own pager", "moderation/templates/moderation/index.html",
     '  {% include "core/admin/_pager.html" with page=items %}',
     '  {% if items.has_next %}<a href="?page={{ items.next_page_number }}">下一页</a>{% endif %}',
     [t("test_custom_admin_lists_share_the_tabs_and_the_pager")]),
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
