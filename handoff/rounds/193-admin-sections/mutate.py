"""Round 193: break each rule once and check its test goes red (AGENTS.md
rule 7). Runs the tests first and stops if they are not green (083).

bash scripts/remote-check.sh run uv run python handoff/rounds/193-admin-sections/mutate.py
"""

import os
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
PY = sys.executable
ENV = {**os.environ, "PYTHONUTF8": "1"}

W = "core/tests/test_admin_wording.py::"
EIGHT = W + "test_the_sidebar_is_eight_sections_without_submenus"
TABS = W + "test_each_section_has_its_tabs_in_order"
ROLES = W + "test_each_role_sees_only_its_sections_and_tabs"
LIGHT = W + "test_every_page_lights_its_own_section"
CSS_RULES = W + "test_the_sidebar_light_follows_the_marker_for_every_section"
COLUMN = W + "test_the_strip_opens_the_content_column"
COUNTS = W + "test_review_tabs_count_what_waits"
STRAIGHT = "tournaments/tests/test_review_admin.py::test_the_tournament_list_leads_straight_to_its_waiting_registrations"
S = "core/admin_sections.py"
TPL = "core/templates/core/admin/section_tabs.html"
CSS = "static/css/admin.css"

MUTATIONS = [
    ("menu left flat", S, "    menu_items[:] = items", "    pass", [EIGHT]),
    ("a tab dropped", S, '("articles", "categories", "pages", "images")', '("articles", "pages", "images")', [TABS]),
    ("articles count as site pages", S, '        return "articles"\n', '        return "pages"\n', [LIGHT]),
    ("scrim notices belong nowhere", S, '    ("announce/scrim/", "scrims"),\n', "", [LIGHT]),
    ("the first page belongs nowhere", S, '    if path == _admin(""):\n        return "home"\n', "", [TABS]),
    ("no 稿件 tab", S, "    if can_approve_submissions(request.user):", "    if False:", [TABS]),
    ("people not under one tab", S, "    if people:", "    if False:", [TABS]),
    ("review tabs uncounted", S, '    if place.section is not None and place.section.key == "review":', "    if False:", [COUNTS]),
    ("the strip lands nowhere", "core/templatetags/admin_sections.py", "MARKER = '<div class=\"content\">'", "MARKER = '<div class=\"contents\">'", [COLUMN, TABS]),
    ("grouped before the submitters' filter", "core/wagtail_hooks.py", '@hooks.register("construct_main_menu", order=1100)', '@hooks.register("construct_main_menu", order=800)', [ROLES]),
    ("no current tab", TPL, '{% if tab is place.tab %} aria-current="page"{% endif %}', "", [TABS, LIGHT]),
    ("a strip for a single page", TPL, "{% if place.section and place.section.tabs|length > 1 %}", "{% if place.section and place.section.tabs|length > 0 %}", [TABS]),
    ("Wagtail's own light left on", CSS, "body:has([data-admin-section]) .sidebar-menu-item--active {", "body:has([data-admin-sections]) .sidebar-menu-item--active {", [CSS_RULES]),
    ("审核 never lit", CSS, 'body:has([data-admin-section="review"]) .sidebar-menu-item:has(> a[data-section="review"])', 'body:has([data-admin-section="reviews"]) .sidebar-menu-item:has(> a[data-section="review"])', [CSS_RULES]),
    ("no 待审核 column", "tournaments/wagtail_hooks.py", '        PendingColumn("pending_registrations", label="待审核"),\n', "", [STRAIGHT]),
    ("nothing counted per tournament", "tournaments/wagtail_hooks.py", 'filter=Q(registrations__status=RegistrationStatus.PENDING),', "filter=Q(pk=None),", [STRAIGHT]),
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
