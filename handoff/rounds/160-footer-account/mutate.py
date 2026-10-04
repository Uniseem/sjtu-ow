"""Round 160: break each new rule once and check its test goes red (AGENTS.md
rule 7). Runs the tests first and stops if they are not green (083).

bash scripts/remote-check.sh run uv run python handoff/rounds/160-footer-account/mutate.py
"""

import os
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
PY = sys.executable
ENV = {**os.environ, "PYTHONUTF8": "1"}

T = "core/tests/test_footer_account.py"


def t(name):
    return f"{T}::{name}"


VISITOR = t("test_visitors_are_offered_sign_in")
MEMBER = t("test_members_get_their_own_pages")
TPL = "templates/slots/footer_account.html"

MUTATIONS = [
    ("everyone gets the visitor links", TPL, "  {% if request.user.is_authenticated %}", "  {% if False %}", [MEMBER]),
    ("everyone gets the member links", TPL, "  {% if request.user.is_authenticated %}", "  {% if True %}", [VISITOR]),
    ("not swapped in place", TPL, '{% if oob %} hx-swap-oob="true"{% endif %}', "", [MEMBER]),
    ("not registered", "core/apps.py", '        register("footer-account", template_slot("slots/footer_account.html"))\n', "", [MEMBER]),
    ("footer written out again", "templates/base.html", '            {% include "slots/footer_account.html" %}\n', '            <nav class="c-footer__col font-nav" aria-label="账号"><h2 class="c-eyebrow">账号</h2><a href="/accounts/login/">登录</a><a href="/accounts/signup/">注册</a></nav>\n', [VISITOR, MEMBER]),
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
