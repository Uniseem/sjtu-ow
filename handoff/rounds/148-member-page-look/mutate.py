"""Round 148: break each new rule once and check its test goes red (AGENTS.md
rule 7). Runs the tests first and stops if they are not green (083).

bash scripts/remote-check.sh run uv run python handoff/rounds/148-member-page-look/mutate.py
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
O = "members/tests/test_own_page.py"
PAGE = "members/templates/members/detail.html"

MUTATIONS = [
    ("no team count", PAGE,
     "            <div><dt>现役战队</dt><dd>{{ page.teams|length }} 支</dd></div>\n", "",
     [f"{T}::test_the_banner_counts_teams_and_articles"]),
    ("no article count", PAGE,
     "            <div><dt>文章</dt><dd>{{ page.article_count }} 篇</dd></div>\n", "",
     [f"{T}::test_the_banner_counts_teams_and_articles"]),
    ("no positions", PAGE,
     "            {% if page.profile.roles %}<div><dt>常用位置</dt>", "            {% if False %}<div><dt>常用位置</dt>",
     [f"{T}::test_the_page_shows_what_is_public_and_nothing_else"]),
    ("no rank", PAGE,
     "{% with rank=page.profile.main_rank %}{% if rank %}<div>", "{% with rank=page.profile.main_rank %}{% if False %}<div>",
     [f"{T}::test_the_page_shows_what_is_public_and_nothing_else"]),
    ("big team cards again", PAGE,
     '          <ol class="c-rows">\n            {% for team in page.teams %}\n',
     '          <ol class="c-rows c-teams--list">\n            {% for team in page.teams %}\n',
     [f"{T}::test_the_banner_counts_teams_and_articles"]),
    ("the owner panel for everyone", PAGE,
     "      {% if is_owner %}\n        {# Design 6.4 (v6.21)", "      {% if True %}\n        {# Design 6.4 (v6.21)",
     [f"{O}::test_only_the_owner_sees_edit_and_hints"]),
    ("no owner panel", PAGE,
     "      {% if is_owner %}\n        {# Design 6.4 (v6.21)", "      {% if False %}\n        {# Design 6.4 (v6.21)",
     [f"{O}::test_only_the_owner_sees_edit_and_hints"]),
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
