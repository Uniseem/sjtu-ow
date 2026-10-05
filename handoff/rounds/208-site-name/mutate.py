"""Round 208: break each rule once and check its test goes red (AGENTS.md
rule 7). Runs the tests first and stops if they are not green (083).
``--check`` only looks that every mutation still applies.

bash scripts/remote-check.sh run uv run python handoff/rounds/208-site-name/mutate.py
"""

import os
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
PY = sys.executable
ENV = {**os.environ, "PYTHONUTF8": "1"}

N = "core/tests/test_site_name.py::"
LEFT = N + "test_no_old_name_is_left"
TITLES = N + "test_every_page_title_ends_with_the_name"
SAYS = N + "test_the_pages_letters_and_settings_say_sjtu_ow"
STORED = N + "test_stored_old_defaults_follow_and_changed_ones_stay"
LETTERS = "core/tests/test_letters.py"

MUTATIONS = [
    ("the old short name in the header", "templates/components/brand.html",
     '<span class="c-brand__name">SJTU-OW</span>',
     '<span class="c-brand__name">交大守望先锋</span>', [LEFT, SAYS]),
    ("a page title with the old suffix", "teams/templates/teams/index.html",
     "· SJTU-OW{% endblock %}", "· 上海交通大学守望先锋社区{% endblock %}", [LEFT, TITLES]),
    ("a page title without the name", "tournaments/templates/tournaments/register.html",
     "{{ tournament.title }} · SJTU-OW{% endblock %}", "{{ tournament.title }}{% endblock %}",
     [TITLES]),
    ("the old signature on letters", "core/letters.py",
     'SIGNATURE = "SJTU-OW"', 'SIGNATURE = "上海交通大学守望先锋社区"', [LEFT, SAYS, LETTERS]),
    ("the old prefix by default", "core/mail.py",
     'DEFAULT_SUBJECT_PREFIX = "[SJTU-OW]"', 'DEFAULT_SUBJECT_PREFIX = "[SJTU OW]"', [LEFT]),
    ("no share-card site name", "templates/base.html",
     """    <meta property="og:site_name" content="{{ seo.site_name|default:'SJTU-OW' }}">\n""",
     "", [SAYS]),
    ("the hero keeps the old two lines", "content/templates/content/home_page.html",
     "<span>SJTU-</span><span>OW</span>", "<span>上海交通</span><span>大学</span>", [SAYS]),
    ("stored defaults stay old", "core/migrations/0024_site_name_sjtu_ow.py",
     '    ("core", "SiteSettings", "from_name", "SJTU 守望先锋社区", "SJTU-OW"),\n', "",
     [STORED]),
    ("the owner's own prefix overwritten", "core/migrations/0024_site_name_sjtu_ow.py",
     "        apps.get_model(app, model).objects.filter(**{field: old}).update(**{field: new})",
     "        apps.get_model(app, model).objects.update(**{field: new})", [STORED]),
]


def run(tests):
    return subprocess.run(
        [PY, "-m", "pytest", "-q", "-x", "-p", "no:cacheprovider", *tests],
        cwd=ROOT,
        env=ENV,
        capture_output=True,
        text=True,
    ).returncode


def _text(rel):
    return (ROOT / rel).read_bytes().decode("utf-8").replace("\r\n", "\n")


def check():
    bad = [
        (label, _text(rel).count(old))
        for label, rel, old, _new, _tests in MUTATIONS
        if _text(rel).count(old) != 1
    ]
    print("mutations:", len(MUTATIONS), "not applying:", bad or "none")
    return not bad


def main():
    if not check():
        sys.exit(1)
    if "--check" in sys.argv:
        return
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
            text = raw.replace("\r\n", "\n").replace(old, new)
            path.write_bytes(
                (text.replace("\n", "\r\n") if crlf else text).encode("utf-8")
            )
            for test in tests:
                red = run([test]) != 0
                name = test.split("::")[-1]
                print(("caught " if red else "MISSED ") + label + " -> " + name)
                if not red:
                    failed.append((label, test))
        finally:
            shutil.copy2(backup, path)
            backup.unlink()
            folder = rel.rsplit("/", 1)[0]
            for cache in ROOT.glob(folder + "/**/__pycache__/*.pyc"):
                cache.unlink()
    assert run(every) == 0, "not green after restoring"
    print("restored and green;", "missed:", failed or "none")


if __name__ == "__main__":
    main()
