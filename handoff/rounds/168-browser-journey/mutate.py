"""Round 168: break each new rule once and check its test goes red (AGENTS.md
rule 7). Runs the tests first and stops if they are not green (083).

bash scripts/remote-check.sh run uv run python handoff/rounds/168-browser-journey/mutate.py
"""

import os
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
PY = sys.executable
ENV = {**os.environ, "PYTHONUTF8": "1"}

T = "teams/tests/test_form_errors_once.py"


def t(name):
    return f"{T}::{name}"


ONCE = t("test_the_apply_page_says_it_once")
GUARD = t("test_no_page_repeats_what_the_shared_form_says")
DOUBLE = '      {% if form.non_field_errors %}<p class="c-field__error">{{ form.non_field_errors.0 }}</p>{% endif %}\n'

MUTATIONS = [
    ("apply says it twice again", "teams/templates/teams/apply.html", '        {% include "account/_form.html" %}\n', DOUBLE + '        {% include "account/_form.html" %}\n', [ONCE, GUARD]),
    ("create says it twice again", "teams/templates/teams/create.html", '      {% include "account/_form.html" %}\n', DOUBLE + '      {% include "account/_form.html" %}\n', [GUARD]),
    ("the shared form stays silent", "templates/account/_form.html", "{% if form.non_field_errors %}", "{% if False %}", [ONCE]),
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
