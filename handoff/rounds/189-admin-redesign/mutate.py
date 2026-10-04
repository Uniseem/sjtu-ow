"""Round 189: break each new rule once and check its test goes red (AGENTS.md
rule 7). Runs the tests first and stops if they are not green (083).

bash scripts/remote-check.sh run uv run python handoff/rounds/189-admin-redesign/mutate.py
"""

import os
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
PY = sys.executable
ENV = {**os.environ, "PYTHONUTF8": "1"}

L = "core/tests/test_admin_look.py::"
TOKENS = L + "test_the_admin_uses_the_sites_colour_values_light_and_dark"
MAPPING = L + "test_wagtails_colours_point_at_the_tokens"
LOADED = L + "test_every_admin_page_loads_the_look_and_the_sites_mark"
FIRST = L + "test_the_first_page_greets_and_offers_the_usual_work"
BUTTONS = L + "test_each_role_gets_its_own_buttons"
W = "core/tests/test_admin_wording.py::"
ORDER = W + "test_the_menu_follows_the_design_order"
ROLES = W + "test_each_role_sees_only_its_own_work"
HIDDEN = W + "test_wagtails_unused_entries_stay_out_of_every_menu"
CSS = "static/css/admin.css"
HOME = "core/admin_home.py"
HOOKS = "core/wagtail_hooks.py"

MUTATIONS = [
    ("look not loaded", HOOKS, '''    return format_html('<link rel="stylesheet" href="{}">', static("css/admin.css"))''', '''    return ""''', [LOADED]),
    ("light red drifts", CSS, "  --sj-primary: #9b3a33;\n", "  --sj-primary: #9b3a34;\n", [TOKENS]),
    ("dark ground drifts", CSS, "    --sj-bg: #141a24;\n    --sj-surface: #1a2130;", "    --sj-bg: #141a25;\n    --sj-surface: #1a2130;", [TOKENS]),
    ("sidebar stays purple", CSS, "  --w-color-surface-menus: var(--sj-surface);\n", "  --w-color-surface-menus: var(--w-color-primary);\n", [MAPPING]),
    ("bird stays", "templates/wagtailadmin/base.html", '<span class="a-brand">', "<span>", [LOADED]),
    ("sidebar re-sorts", HOME, "        item.order = number * 10\n", "        pass\n", [ORDER]),
    ("社区 kept whole", HOME, "        if isinstance(item, SubmenuMenuItem) and item.label in FLATTENED:\n", "        if False:\n", [ORDER, HIDDEN]),
    ("reports back", HOME, 'MAIN_HIDDEN = frozenset({"documents", "reports", "help"})\n', 'MAIN_HIDDEN = frozenset({"documents", "help"})\n', [HIDDEN]),
    ("settings unsorted", HOME, "    items = [item for item in menu_items if item.label in SETTINGS_KEPT]\n", "    items = list(menu_items)\n", [ORDER, HIDDEN]),
    ("page tree for everyone", HOME, "    if explorer is not None and _edits_every_page(user):\n", "    if explorer is not None:\n", [ROLES]),
    ("no 文章", HOME, "    news = _news_index() if explorer is not None else None\n", "    news = None\n", [ORDER, ROLES]),
    ("no tournament button", HOME, '        found.append(Action("新建赛事", reverse("tournaments:add"), primary=not found))\n', "", [FIRST, BUTTONS]),
    ("Wagtail panels kept", HOOKS, "    panels[:] = own\n", "    panels[0:0] = own\n", [FIRST]),
    ("no greeting", HOOKS, "    own = [WelcomePanel()]\n", "    own = []\n", [FIRST, BUTTONS]),
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
