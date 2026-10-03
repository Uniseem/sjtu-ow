"""Round 105: break each new rule once and check its test goes red (AGENTS.md
rule 7). Runs the tests first and stops if they are not green (083).

uv run python handoff/rounds/105-cache-latency/mutate.py
"""

import os
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
PY = sys.executable
ENV = {**os.environ, "PYTHONUTF8": "1"}

T = "core/tests/test_latency.py"
AUDIT = "core/tests/test_chapter15_audit.py"
CADDY = "deploy/Caddyfile"
RULES = "templates/components/speculation_rules.html"
SAME = f"{T}::test_prerendered_pages_carry_the_same_policy_as_django"
PAGES = f"{T}::test_pages_ask_the_browser_to_prepare_public_links"

MUTATIONS = [
    ("Caddy's policy drifts from Django's", CADDY,
     "script-src 'self' 'inline-speculation-rules'; style-src",
     "script-src 'self'; style-src", [SAME]),
    ("prerendered pages lose the security headers", CADDY,
     "\t\timport page_security\n", "", [SAME]),
    ("prerendered pages may be framed", CADDY,
     '\t\tX-Frame-Options "DENY"\n', "", [SAME]),
    ("precompressed comes back", CADDY,
     '\t\troot * /srv/prerendered\n\t\trewrite * {path}/index.html\n',
     '\t\troot * /srv/prerendered\n\t\trewrite * {path}/index.html\n\t\tfile_server {\n\t\t\tprecompressed br gzip\n\t\t}\n',
     [f"{T}::test_caddy_does_not_serve_precompressed_files"]),
    ("thumbnails lose their year", CADDY,
     '\t\theader Cache-Control "public, max-age=31536000, immutable"\n\t\tfile_server\n\t}\n\n\thandle /media/* {',
     '\t\tfile_server\n\t}\n\n\thandle /media/* {',
     [f"{T}::test_thumbnails_are_kept_a_year_and_other_uploads_a_day"]),
    ("other uploads lose their day", CADDY,
     '\t\theader Cache-Control "public, max-age=86400"\n', "",
     [f"{T}::test_thumbnails_are_kept_a_year_and_other_uploads_a_day"]),
    ("the policy forbids speculation rules", "sjtu_ow/settings/base.py",
     '"script-src": [CSP.SELF, "\'inline-speculation-rules\'"],',
     '"script-src": [CSP.SELF],',
     [f"{AUDIT}::test_the_front_end_csp_forbids_inline_script_and_eval", SAME]),
    ("pages carry no rules", "templates/base.html",
     '    {% include "components/speculation_rules.html" %}\n', "",
     [PAGES, f"{T}::test_prerendered_files_carry_the_rules_too"]),
    ("the personal pages are prepared too", RULES, '"/me/*", ', "", [PAGES]),
    ("the sign-in pages are prepared too", RULES, '"/accounts/*", ', "", [PAGES]),
    ("downloads are prepared", RULES, "[download], ", "", [PAGES]),
    ("everything is prepared at once", RULES, '"moderate"', '"immediate"', [PAGES]),
    ("a prepared page asks before it is shown", "static/js/state.js",
     "    if (d.prerendering) {\n"
     '      d.addEventListener("prerenderingchange", start, { once: true });\n'
     "    } else {\n      start();\n    }\n",
     "    start();\n",
     [f"{T}::test_a_prepared_page_waits_to_be_shown_before_asking_who_is_signed_in"]),
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
