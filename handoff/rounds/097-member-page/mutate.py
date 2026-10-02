"""Round 097: break each new rule once and check its test goes red (AGENTS.md
rule 7). Runs the tests first and stops if they are not green (083).

uv run python handoff/rounds/097-member-page/mutate.py
"""

import os
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
PY = sys.executable
ENV = {**os.environ, "PYTHONUTF8": "1"}

T = "members/tests/test_member_page.py"
PAGE = "members/templates/members/detail.html"

MUTATIONS = [
    ("anyone gets a page", "members/views.py",
     "    user = joined_users().filter(pk=pk)",
     "    user = joined_users().model.objects.filter(pk=pk)",
     [f"{T}::test_only_the_people_on_the_showcase_have_a_page"]),
    ("search engines may index it", PAGE,
     '  <meta name="robots" content="noindex">\n', "",
     [f"{T}::test_the_page_stays_out_of_search_engines"]),
    ("the game ID is shown", PAGE,
     "          <h1>{{ page.user.nickname }}</h1>\n",
     "          <h1>{{ page.user.nickname }}</h1>"
     "{{ page.user.game_accounts.first.battletag }}\n",
     [f"{T}::test_the_page_shows_what_is_public_and_nothing_else"]),
    ("the teams left are dropped", "members/services.py",
     "        alumni=alumni,\n", "        alumni=[],\n",
     [f"{T}::test_current_teams_and_the_ones_left"]),
    ("how they left is public", PAGE,
     '<time datetime="{{ record.left_at|date:\'c\' }}">',
     '{{ record.get_reason_display }}<time datetime="{{ record.left_at|date:\'c\' }}">',
     [f"{T}::test_current_teams_and_the_ones_left"]),
    ("drafts are listed", "members/services.py",
     "        ArticlePage.objects.live()\n        .public()\n        .filter(author=user)",
     "        ArticlePage.objects.filter(author=user)",
     [f"{T}::test_the_articles_they_wrote"]),
    ("a card opens nothing", "members/templates/members/index.html",
     '<a href="{{ member.user|member_url }}" class="c-person__name c-stretch"',
     '<a class="c-person__name c-stretch"',
     [f"{T}::test_every_card_on_the_showcase_opens_the_page"]),
    ("the byline is plain text", "content/templates/content/article_page.html",
     '{% if url %}<a href="{{ url }}">{{ page.author.nickname }}</a>',
     '{% if False %}<a href="{{ url }}">{{ page.author.nickname }}</a>',
     [f"{T}::test_the_team_page_and_the_byline_lead_to_it"]),
    ("the deactivated are linked", "core/templatetags/ow.py",
     '    if user is None or not getattr(user, "is_active", False):',
     "    if user is None:",
     [f"{T}::test_someone_without_a_page_is_not_linked"]),
    ("search sends members to the list", "search/services.py",
     "            title=user.nickname, url=member_url(user), excerpt=user.motto, meta=\"成员\"",
     "            title=user.nickname, url=\"/members/\", excerpt=user.motto, meta=\"成员\"",
     ["search/tests/test_search.py::test_members_are_the_people_on_the_members_page"]),
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
