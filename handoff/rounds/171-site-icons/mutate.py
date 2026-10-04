"""Round 171: break each new rule once and check its test goes red (AGENTS.md
rule 7). Runs the tests first and stops if they are not green (083).

bash scripts/remote-check.sh run uv run python handoff/rounds/171-site-icons/mutate.py
"""

import os
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
PY = sys.executable
ENV = {**os.environ, "PYTHONUTF8": "1"}

T = "core/tests/test_site_icons.py"


def t(name):
    return f"{T}::{name}"


SHAPE = t("test_each_png_is_the_svg_shape")
ICO = t("test_the_ico_has_three_sizes")
SAME = t("test_the_committed_files_are_what_the_code_draws")
PAGES = t("test_pages_point_at_them_and_the_root_addresses_lead_there")
RESERVED = "content/tests/test_content.py::test_every_fixed_top_level_route_is_reserved"
I = "core/icons.py"

MUTATIONS = [
    ("another red", I, "RED = (164, 22, 26, 255)", "RED = (200, 22, 26, 255)", [SAME, SHAPE]),
    ("chevron lower", I, "CHEVRON = [(8, 21.5), (16, 13.5), (24, 21.5)]", "CHEVRON = [(8, 23.5), (16, 15.5), (24, 23.5)]", [SAME]),
    ("iOS icon rounded", I, '    ("apple-touch-icon.png", 180, False),', '    ("apple-touch-icon.png", 180, True),', [SHAPE, SAME]),
    ("no 16px", I, "ICO_SIZES = (16, 32, 48)", "ICO_SIZES = (32, 48)", [SAME]),
    ("no apple link", "templates/base.html", "    <link rel=\"apple-touch-icon\" href=\"{% static 'img/apple-touch-icon.png' %}\">\n", "", [PAGES]),
    ("no manifest link", "templates/base.html", "    <link rel=\"manifest\" href=\"{% static 'manifest.webmanifest' %}\">\n", "", [PAGES]),
    ("a temporary redirect", "core/views.py", '    return redirect(static(f"img/{name}"), permanent=True)', '    return redirect(static(f"img/{name}"))', [PAGES]),
    ("no root favicon", "core/urls.py", '    path("favicon.ico", views.site_icon, {"name": "favicon.ico"}),\n', "", [PAGES]),
    ("favicon not reserved", "content/models.py", '        "favicon.ico",\n', "", [RESERVED]),
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
