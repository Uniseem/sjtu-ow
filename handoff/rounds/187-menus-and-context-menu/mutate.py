"""Round 187: break each new rule once and check its test goes red (AGENTS.md
rule 7). Runs the tests first and stops if they are not green (083).

bash scripts/remote-check.sh run uv run python handoff/rounds/187-menus-and-context-menu/mutate.py
"""

import os
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
PY = sys.executable
ENV = {**os.environ, "PYTHONUTF8": "1"}

T = "core/tests/test_menus_and_context_menu.py"


def t(name):
    return f"{T}::{name}"


LOADED = t("test_every_front_page_loads_the_menu_script")
NATIVE = t("test_the_browser_menu_stays_where_it_is_needed")
OFFERS = t("test_it_offers_what_the_design_lists")
KEYS = t("test_it_closes_and_moves_by_keyboard")
DROPDOWNS = t("test_the_dropdowns_close_on_outside_clicks_esc_and_each_other")
GUIDE = t("test_the_style_guide_shows_the_context_menu")
CM = "static/js/contextmenu.js"
APP = "static/js/app.js"

MUTATIONS = [
    ("script not loaded", "templates/base.html", "    <script src=\"{% static 'js/contextmenu.js' %}\"></script>\n", "", [LOADED]),
    ("shift no longer gives the browser menu", CM, "if (event.shiftKey || touch ||", "if (touch ||", [NATIVE]),
    ("form fields taken over", CM, 'var NATIVE = "input, textarea, select, ', 'var NATIVE = "', [NATIVE]),
    ("long press taken over", CM, '    var touch = event.pointerType === "touch" || event.pointerType === "pen";\n', "    var touch = false;\n", [NATIVE]),
    ("phones taken over", CM, '!window.matchMedia("(pointer: fine)").matches', "false", [NATIVE]),
    ("no image actions", CM, '        ["在新标签页打开图片",', '        ["打开",', [OFFERS]),
    ("no Esc", CM, '    if (event.key === "Escape" || event.key === "Tab") {', '    if (event.key === "Tab") {', [KEYS]),
    ("opening one leaves the other open", APP, "        closeDropdowns(target);\n", "", [DROPDOWNS]),
    ("outside clicks ignored", APP, "    closeDropdowns(inside);\n", "", [DROPDOWNS]),
    ("Esc leaves the dropdown open", APP, "      open.open = false;\n      var summary", "      var summary", [DROPDOWNS]),
    ("style guide without it", "core/templates/core/styleguide.html", '      <div class="c-ctxmenu static mt-8 w-max" role="presentation">', '      <div class="mt-8 w-max" role="presentation">', [GUIDE]),
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
