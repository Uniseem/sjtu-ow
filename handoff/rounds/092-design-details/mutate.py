"""Round 092: break each new rule once and check its test goes red (AGENTS.md
rule 7). Runs the tests first and stops if they are not green (083).

uv run python handoff/rounds/092-design-details/mutate.py
"""

import os
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
PY = sys.executable
ENV = {**os.environ, "PYTHONUTF8": "1"}

PP = "accounts/tests/test_public_profile.py"
AR = "teams/tests/test_alumni_and_recruiting.py"
MC = "members/tests/test_member_cards.py"
AH = "content/tests/test_article_head.py"
MO = "moderation/tests/test_motto.py"
CP = "core/tests/test_cover_placeholders.py"

MUTATIONS = [
    ("the lowest rank wins", "accounts/roles.py",
     "if role not in best or score > best[role].score:",
     "if role not in best or score < best[role].score:",
     [f"{PP}::test_each_position_shows_its_best_rank_over_every_game_id"]),
    ("ranks never go stale", "accounts/roles.py",
     "STALE_AFTER = timedelta(days=180)", "STALE_AFTER = timedelta(days=3650)",
     [f"{PP}::test_a_rank_older_than_180_days_is_marked_stale"]),
    ("the rank switch is ignored", "accounts/roles.py",
     "    if not user.show_rank:\n        return profile\n", "",
     [f"{PP}::test_turning_the_switch_off_hides_every_rank_but_not_the_positions",
      f"{AR}::test_a_hidden_rank_stays_off_the_team_page"]),
    ("links allowed in the motto", "accounts/forms.py",
     "        if LINK_IN_TEXT.search(motto):", "        if False:",
     [f"{PP}::test_the_profile_form_keeps_the_motto_on_one_line_without_links"]),
    ("the main position repeats as flex", "accounts/forms.py",
     "for role in parse_roles(cleaned.get(\"flex_roles\", \"\")) if role != main",
     "for role in parse_roles(cleaned.get(\"flex_roles\", \"\"))",
     [f"{PP}::test_the_main_position_is_not_repeated_as_a_flex_one"]),
    ("initials take any first character", "core/templatetags/ow.py",
     "        if char.isalnum():", "        if char.strip():",
     [f"{PP}::test_initials_skip_symbols_and_take_a_letter_or_a_character"]),
    ("leaving leaves no record", "teams/services.py",
     "    _retire(membership, LeaveReason.LEFT)\n", "",
     [f"{AR}::test_leaving_and_being_removed_are_recorded_as_alumni"]),
    ("rejoining keeps the record", "teams/services.py",
     "            _unretire(team, application.applicant)\n", "",
     [f"{AR}::test_coming_back_takes_the_person_off_the_alumni"]),
    ("account deletion keeps alumni", "teams/services.py",
     "    for alumnus in list(user.team_alumni.select_related(\"team\")):\n        alumnus.delete()\n        on_team_changed(alumnus.team)\n", "",
     [f"{AR}::test_deleting_an_account_takes_its_alumni_records"]),
    ("anyone may take a record off", "teams/services.py",
     "        actor.pk == alumnus.user_id\n", "        True\n",
     [f"{AR}::test_only_the_person_or_the_captain_can_take_a_record_off"]),
    ("the public page says how they left", "teams/templates/teams/_alumnus.html",
     "{{ alumnus.user.nickname }}</span>", "{{ alumnus.user.nickname }}</span><span>{{ alumnus.get_reason_display }}</span>",
     [f"{AR}::test_the_team_page_lists_the_roster_and_the_alumni_with_their_months"]),
    ("short positions shown while not recruiting", "teams/models.py",
     "        if not self.is_recruiting:\n            return []\n", "",
     [f"{AR}::test_short_positions_show_only_while_recruiting"]),
    ("one field, one post", "members/services.py",
     'TITLE_SEPARATORS = re.compile(r"[、/／,，;；]+")', 'TITLE_SEPARATORS = re.compile(r"[|]+")',
     [f"{MC}::test_one_field_can_hold_several_posts"]),
    ("posts of any length", "members/models.py",
     "if any(len(title) > 10 for title in split_titles(self.title)):",
     "if any(len(title) > 99 for title in split_titles(self.title)):",
     [f"{MC}::test_each_post_is_ten_characters_at_most"]),
    ("every post listed", "members/templates/members/index.html",
     '{% for title in titles|slice:":3" %}', '{% for title in titles %}',
     [f"{MC}::test_more_than_three_posts_and_two_teams_are_counted_not_listed"]),
    ("group names over posts", "members/services.py",
     "        return self.titles or self.groups", "        return self.groups or self.titles",
     [f"{MC}::test_the_roster_card_shows_posts_across_groups"]),
    ("picture after the words", "members/templates/members/index.html",
     '                  <span class="c-person__pic c-hue-{{ member.user|hue }}" aria-hidden="true">{{ member.user.nickname|initial }}</span>\n',
     "",
     [f"{MC}::test_a_card_shows_its_groups_posts_motto_play_and_teams"]),
    ("punctuation counted as words", "content/article_meta.py",
     "    return len(CJK.findall(text)) + len(LATIN_WORD.findall(text))",
     "    return len(\"\".join(text.split()))",
     [f"{AH}::test_words_count_chinese_characters_and_latin_words"]),
    ("a slower reader", "content/article_meta.py",
     "CHARS_PER_MINUTE = 400", "CHARS_PER_MINUTE = 300",
     [f"{AH}::test_reading_time_is_400_a_minute_plus_pictures_and_videos"]),
    ("contents from two headings", "content/article_meta.py",
     "TOC_MIN_HEADINGS = 3", "TOC_MIN_HEADINGS = 2",
     [f"{AH}::test_contents_appear_from_three_headings"]),
    ("any edit counts as updated", "content/models.py",
     "last - first > timedelta(days=1)", "last > first",
     [f"{AH}::test_an_edit_a_day_later_is_shown_as_updated"]),
    ("mottos skip review", "moderation/signals.py",
     "    integrations.submit_motto(instance)\n", "",
     [f"{MO}::test_a_motto_goes_to_review_and_an_empty_one_does_not"]),
    ("the clear box does nothing", "moderation/admin_views.py",
     '    if request.POST.get("clear_motto") and item.target_type == TargetType.MOTTO:',
     "    if False:",
     [f"{MO}::test_a_reviewer_can_clear_a_motto_and_nothing_else"]),
    ("a motto change regenerates nothing", "accounts/signals.py",
     'PUBLIC_FIELDS = ("nickname", "motto", "main_role", "flex_roles", "show_rank")',
     'PUBLIC_FIELDS = ("nickname", "main_role", "flex_roles", "show_rank")',
     [f"{MO}::test_changing_what_the_cards_print_regenerates_the_member_page"]),
    ("private ranks regenerate pages", "accounts/signals.py",
     "    if raw or not instance.user.show_rank:", "    if raw:",
     [f"{MO}::test_a_new_rank_regenerates_the_pages_unless_it_is_private"]),
    ("the export forgets the motto", "accounts/services.py",
     '            "motto": user.motto,\n', "",
     [f"{MO}::test_the_export_carries_the_profile_and_the_alumni_records"]),
    ("a base picture missing from its class", "assets/css/input.css",
     'background: var(--color-info-soft) url("../img/placeholders/hue-3.svg") center / cover;',
     "background: var(--color-info-soft);",
     [f"{CP}::test_the_stylesheet_puts_each_base_picture_on_its_class"]),
    ("the front ridge is not the footer's ground", "core/placeholders.py",
     'RIDGE_SHADES = ("#20242b", "#171a20", "#0e1014")',
     'RIDGE_SHADES = ("#20242b", "#171a20", "#111111")',
     [f"{CP}::test_the_footer_ridge_is_drawn_in_the_night_colours"]),
    ("a detail page goes full width again", "tournaments/templates/tournaments/detail.html",
     '<div class="l-container l-container--narrow l-section">',
     '<div class="l-container l-section">',
     ["core/tests/test_design_system.py::test_pages_to_read_and_act_on_sit_in_a_centred_column[tournaments/templates/tournaments/detail.html]"]),
    ("the centred column as wide as the page", "assets/css/input.css",
     "  .l-container--narrow {\n    max-width: 80rem;",
     "  .l-container--narrow {\n    max-width: 120rem;",
     ["core/tests/test_design_system.py::test_pages_to_read_and_act_on_sit_in_a_centred_column[scrims/templates/scrims/detail.html]"]),
    ("the team banner without its picture", "teams/templates/teams/detail.html",
     '<img class="c-stage__img" src="{{ team|hue_scene }}" width="1600" height="900" alt="">',
     "",
     [f"{AR}::test_team_cards_lead_with_the_picture"]),
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
            for cache in ROOT.glob(rel.rsplit("/", 1)[0] + "/__pycache__/*.pyc"):
                cache.unlink()
    assert run(every) == 0, "not green after restoring"
    print("restored and green;", "missed:", failed or "none")
    return 1 if failed else 0


sys.exit(main())
