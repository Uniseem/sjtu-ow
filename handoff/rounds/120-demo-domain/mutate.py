"""Round 120: break each new rule once and check its test goes red (AGENTS.md
rule 7). Runs the tests first and stops if they are not green (083).

uv run python handoff/rounds/120-demo-domain/mutate.py
"""

import os
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
PY = sys.executable
ENV = {**os.environ, "PYTHONUTF8": "1"}

T = "core/tests/test_client_ip.py"


def t(name):
    return f"{T}::{name}"


MUTATIONS = [
    ("the visitor is Caddy again", "core/ratelimit.py",
     '    return request.headers.get("X-Real-IP", "").strip() or request.META.get(\n',
     '    return request.headers.get("X-Nobody", "").strip() or request.META.get(\n',
     [t("test_the_visitor_is_whoever_caddy_names"), "search/tests/test_search.py::test_the_page_is_rate_limited_per_ip"]),
    ("the last X-Forwarded-For entry wins", "core/ratelimit.py",
     '    return request.headers.get("X-Real-IP", "").strip() or request.META.get(\n',
     '    return request.headers.get("X-Forwarded-For", "").split(",")[-1].strip() or request.META.get(\n',
     [t("test_x_forwarded_for_alone_names_nobody")]),
    ("allauth counts everyone together", "accounts/adapter.py",
     "        return client_ip(request) or super().get_client_ip(request)\n",
     '        return request.META.get("REMOTE_ADDR", "")\n',
     [t("test_allauth_asks_the_same_question"), t("test_failed_logins_count_per_visitor")]),
    ("Caddy does not name the visitor", "deploy/Caddyfile",
     "\t\theader_up X-Real-IP {client_ip}\n", "",
     [t("test_every_route_to_django_names_the_visitor")]),
    ("one route bypasses the snippet", "deploy/Caddyfile",
     "\thandle {\n\t\timport django\n\t}\n", "\thandle {\n\t\treverse_proxy web:8000\n\t}\n",
     [t("test_every_route_to_django_names_the_visitor")]),
    ("the login page hides whole-form errors", "templates/account/_form.html",
     "{% if form.non_field_errors %}\n", "{% if False %}\n",
     [t("test_failed_logins_count_per_visitor")]),
    ("contacts show the error twice", "templates/me/contacts.html",
     '      {% include "account/_form.html" %}\n',
     '      {% if form.non_field_errors %}<p class="c-field__error" role="alert">{{ form.non_field_errors.0 }}</p>{% endif %}\n      {% include "account/_form.html" %}\n',
     [t("test_a_whole_form_error_shows_once")]),
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
