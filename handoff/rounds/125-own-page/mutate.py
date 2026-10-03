"""Round 125: break each new rule once and check its test goes red (AGENTS.md
rule 7). Runs the tests first and stops if they are not green (083).

uv run python handoff/rounds/125-own-page/mutate.py
"""

import os
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
PY = sys.executable
ENV = {**os.environ, "PYTHONUTF8": "1"}

T = "members/tests/test_own_page.py"
PAGE = "members/templates/members/detail.html"


def t(name):
    return f"{T}::{name}"


MUTATIONS = [
    ("no way from the personal centre", "templates/me/base.html",
     '<a href="{% url \'member_detail\' request.user.pk %}" class="c-link text-sm" data-own-page>我的主页</a>', "",
     [t("test_the_personal_centre_links_to_my_page")]),
    ("everyone is the owner", "members/views.py",
     '            "is_owner": request.user.is_authenticated and request.user.pk == user.pk,\n',
     '            "is_owner": True,\n',
     [t("test_only_the_owner_sees_edit_and_hints")]),
    ("no motto hint", PAGE,
     "{% elif is_owner %}<p class=\"text-sm text-fg-2\" data-owner-hint>还没写个人宣言", "{% elif False %}<p class=\"text-sm text-fg-2\" data-owner-hint>还没写个人宣言",
     [t("test_only_the_owner_sees_edit_and_hints")]),
    ("the role hint shows anyway", PAGE,
     "{% if is_owner and not page.user.main_role and not page.user.flex_roles %}", "{% if is_owner %}",
     [t("test_filled_in_parts_need_no_hint")]),
    ("no team hint", PAGE,
     '{% if is_owner %}<a href="{% url \'team_index\' %}" class="c-link" data-owner-hint>去找一支招募中的</a>{% endif %}', "",
     [t("test_only_the_owner_sees_edit_and_hints")]),
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
