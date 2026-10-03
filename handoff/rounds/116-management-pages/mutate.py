"""Round 116: break each new rule once and check its test goes red (AGENTS.md
rule 7). Runs the tests first and stops if they are not green (083).

uv run python handoff/rounds/116-management-pages/mutate.py
"""

import os
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
PY = sys.executable
ENV = {**os.environ, "PYTHONUTF8": "1"}

T = "core/tests/test_management_pages.py"
MANAGE = "teams/templates/teams/manage.html"


def t(name):
    return f"{T}::{name}"


MUTATIONS = [
    ("members without positions and ranks", MANAGE,
     '                <td data-label="位置与段位">{% include "components/play_style.html" with profile=membership.user|public_profile %}</td>\n',
     "",
     [t("test_the_captain_sees_ranks_of_members_and_applicants")]),
    ("applicants without ranks", MANAGE,
     "：{{ account|rank_summary }}</li>", "</li>",
     [t("test_the_captain_sees_ranks_of_members_and_applicants")]),
    ("disband blockers hidden until the button", MANAGE,
     "            {% if disband_blockers %}\n", "            {% if False %}\n",
     [t("test_a_team_that_cannot_disband_says_why_before_the_button")]),
    ("the create page shows the form anyway", "teams/templates/teams/create.html",
     "    {% if blocker %}\n", "    {% if False %}\n",
     [t("test_the_create_page_says_no_before_the_form")]),
    ("a refused team keeps its logo", "teams/views.py",
     "    if logo is not None:\n        logo.delete()\n", "    return None\n",
     [t("test_a_refused_team_leaves_no_logo_and_names_the_field")]),
    ("the snapshot has no ranks", "tournaments/templates/tournaments/registration_detail.html",
     '                <td data-label="段位（提交时）" class="text-sm">{{ member|rank_summary }}</td>\n', "",
     [t("test_the_roster_snapshot_and_the_admin_show_ranks")]),
    ("the admin shows rank codes", "tournaments/templates/tournaments/admin/review_detail.html",
     "<td>{{ row.member.rank_damage|rank_label }}</td>", "<td>{{ row.member.rank_damage }}</td>",
     [t("test_the_roster_snapshot_and_the_admin_show_ranks")]),
    ("rosters I left are listed", "tournaments/registration.py",
     "        Registration.objects.filter(members__user=user, members__is_active=True)\n",
     "        Registration.objects.filter(members__user=user)\n",
     [t("test_my_registrations_lists_rosters_i_am_on_and_my_signups_in_full")]),
    ("a finished tournament still waits for a team", "templates/me/registrations.html",
     '                {% elif signup.tournament.status == "finished" %}\n',
     '                {% elif False %}\n',
     [t("test_my_registrations_lists_rosters_i_am_on_and_my_signups_in_full")]),
    ("the password page has no way back", "templates/account/password_change.html",
     '  {% include "account/_back_to_security.html" with here="修改密码" %}\n', "",
     [t("test_password_and_email_pages_lead_back_to_account_security")]),
    ("no logout on account security", "templates/me/security.html",
     "        <form method=\"post\" action=\"{% url 'account_logout' %}\">", "        <form method=\"post\" action=\"/nowhere/\">",
     [t("test_password_and_email_pages_lead_back_to_account_security")]),
    ("signup without the agreement links", "templates/account/signup.html",
     '<a href="/privacy/" class="c-link" target="_blank" rel="noopener">隐私政策</a>', "隐私政策",
     [t("test_signup_links_the_agreement_and_the_privacy_policy")]),
    ("the export is a download attribute again", "templates/me/security.html",
     'class="c-btn c-btn--secondary" data-no-loading>', 'class="c-btn c-btn--secondary" download>',
     [t("test_the_export_link_is_not_a_download_attribute")]),
    ("an individual signup calls you by name", "tournaments/registration.py",
     "    problems.extend(member_problems(tournament=tournament, user=user, as_self=True))\n",
     "    problems.extend(member_problems(tournament=tournament, user=user))\n",
     [t("test_an_individual_signup_speaks_to_the_person")]),
    ("signup notices without links", "tournaments/templates/tournaments/individual_signup.html",
     '            {% include "components/profile_gap_links.html" %}\n', "",
     [t("test_signup_notices_link_to_where_the_profile_is_filled_in")]),
    ("a refused comment loses the box", "comments/views.py",
     "            context[\"draft_body\"] = draft\n",
     "            context[\"draft_body\"] = draft\n            context[\"can_post\"] = False\n",
     [t("test_a_refused_comment_keeps_the_box_and_the_text")]),
    ("a refused comment loses the text", "comments/templates/comments/_composer.html",
     "{% if not parent %}{{ draft_body }}{% endif %}</textarea>", "</textarea>",
     [t("test_a_refused_comment_keeps_the_box_and_the_text")]),
    ("no teams is a bare sentence", "templates/me/teams.html",
     '      {% include "components/empty_state.html" with title="还没有加入战队" message="去战队页看看谁在招人，或者自己创建一支。" action_url=teams_url action_label="去看看战队" %}\n',
     '      <p>还没有加入战队。</p>\n',
     [t("test_empty_lists_use_the_empty_state")]),
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
