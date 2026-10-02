"""Round 101: break each new rule once and check its test goes red (AGENTS.md
rule 7). Runs the tests first and stops if they are not green (083).

uv run python handoff/rounds/101-avatars/mutate.py
"""

import os
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
PY = sys.executable
ENV = {**os.environ, "PYTHONUTF8": "1"}

T = "accounts/tests/test_avatar.py"
AUDIT = "core/tests/test_chapter15_audit.py"
FACE = "templates/components/avatar.html"

MUTATIONS = [
    ("the component ignores the picture", FACE,
     "{% if person.avatar_id %}", "{% if False %}",
     [f"{T}::test_a_face_is_the_picture_when_there_is_one",
      f"{T}::test_the_account_menu_shows_your_own_picture"]),
    ("plain still draws the scene", FACE,
     "{% if not plain %} c-hue-", "{% if True %} c-hue-",
     [f"{T}::test_without_a_picture_a_face_is_the_initial_on_its_scene"]),
    ("a spot draws the face by hand", "teams/templates/teams/_alumnus.html",
     '{% include "components/avatar.html" with person=alumnus.user size="sm" %}',
     '<span class="c-avatar c-avatar--sm c-hue-{{ alumnus.user|hue }}" '
     'aria-hidden="true">{{ alumnus.user.nickname|initial }}</span>',
     [f"{T}::test_no_template_draws_a_face_by_hand",
      f"{T}::test_the_team_page_shows_members_and_former_members"]),
    ("the member card ignores the picture", "members/templates/members/index.html",
     "{% if member.user.avatar_id %}", "{% if False %}",
     [f"{T}::test_the_member_page_shows_the_picture_on_the_card_and_in_the_list"]),
    ("a new picture regenerates nothing", "accounts/signals.py",
     '    "show_rank",\n    "avatar_id",\n', '    "show_rank",\n',
     [f"{T}::test_a_new_picture_regenerates_the_pages_that_show_it"]),
    ("update_fields naming the field is missed", "accounts/signals.py",
     '_PUBLIC_UPDATE_FIELDS = {*PUBLIC_FIELDS, "avatar"}',
     "_PUBLIC_UPDATE_FIELDS = {*PUBLIC_FIELDS}",
     [f"{T}::test_a_new_picture_regenerates_the_pages_that_show_it"]),
    ("former members' team pages go stale", "accounts/services.py",
     "    for alumnus in user.team_alumni.select_related(\"team\"):\n"
     "        if not alumnus.team.is_disbanded:",
     "    for alumnus in user.team_alumni.select_related(\"team\"):\n"
     "        if False:",
     [f"{T}::test_a_former_members_team_page_is_regenerated_too"]),
    ("deletion keeps the picture", "accounts/services.py",
     "        user.avatar = None  # design-details 2.3\n", "",
     [f"{T}::test_deleting_the_account_drops_the_picture"]),
    ("thumbnails are not prefetched", "accounts/services.py",
     '    return queryset.select_related(f"{path}avatar").prefetch_related(\n'
     '        f"{path}avatar__renditions"\n    )',
     '    return queryset.select_related(f"{path}avatar")',
     [f"{T}::test_no_n_plus_one_on_a_team_page"]),
    ("the member list loads faces one by one", "members/services.py",
     "        with_avatars(joined_users())\n", "        joined_users()\n",
     [f"{AUDIT}::test_no_n_plus_one_on_the_member_page"]),
    ("the team page loads members' faces one by one", "teams/views.py",
     '        with_avatars(team.memberships.select_related("user"), "user__")\n',
     '        team.memberships.select_related("user")\n',
     [f"{T}::test_no_n_plus_one_on_a_team_page"]),
    ("the team page loads former members' faces one by one", "teams/views.py",
     '        with_avatars(team.alumni.select_related("user"), "user__")\n',
     '        team.alumni.select_related("user")\n',
     [f"{T}::test_no_n_plus_one_on_a_team_page"]),
    ("the pool loads faces one by one", "tournaments/registration.py",
     "        with_avatars(\n"
     "            tournament.individual_signups.filter(registration__isnull=True),\n"
     '            "user__",\n        )\n',
     "        tournament.individual_signups.filter(registration__isnull=True)\n",
     [f"{T}::test_no_n_plus_one_on_the_individual_pool"]),
    ("comments load faces one by one", "comments/services.py",
     "    base = with_avatars(\n"
     '        page.comments.select_related("author", "reply_to_user"), "author__"\n'
     "    )",
     '    base = page.comments.select_related("author", "reply_to_user")',
     [f"{T}::test_no_n_plus_one_on_an_article_with_comments"]),
    ("the article list loads faces one by one", "content/models.py",
     "        articles = (\n"
     '            with_avatars(ArticlePage.objects.live().public(), "author__")\n',
     "        articles = (\n            ArticlePage.objects.live().public()\n",
     [f"{T}::test_no_n_plus_one_on_the_article_list"]),
    ("cards look up the site root each", "templates/components/post_card.html",
     '<a href="{% pageurl article %}" class="c-stretch" title=',
     '<a href="{{ article.url }}" class="c-stretch" title=',
     [f"{T}::test_no_n_plus_one_on_the_article_list"]),
    ("thumbnails are noted in the database cache", "sjtu_ow/settings/base.py",
     '        "BACKEND": "django.core.cache.backends.locmem.LocMemCache",\n'
     '        "LOCATION": "renditions",\n',
     '        "BACKEND": "django.core.cache.backends.db.DatabaseCache",\n'
     '        "LOCATION": "django_cache",\n',
     [f"{T}::test_no_n_plus_one_on_a_team_page"]),
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
