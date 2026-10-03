"""Round 106: break each new rule once and check its test goes red (AGENTS.md
rule 7). Runs the tests first and stops if they are not green (083).

uv run python handoff/rounds/106-page-transitions/mutate.py
"""

import os
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
PY = sys.executable
ENV = {**os.environ, "PYTHONUTF8": "1"}

T = "core/tests/test_transitions.py"
CSS = "assets/css/input.css"
THEME = "static/js/theme.js"
LOADING = "static/js/loading.js"

MUTATIONS = [
    ("no cross-page transition", CSS,
     "  @view-transition {\n    navigation: auto;\n  }\n", "",
     [f"{T}::test_pages_change_with_the_browsers_cross_page_transition"]),
    ("transitions even with less motion asked for", CSS,
     "@media (prefers-reduced-motion: no-preference) {\n  @view-transition {\n    navigation: auto;\n  }\n",
     "@view-transition {\n  navigation: auto;\n}\n\n@media (prefers-reduced-motion: no-preference) {\n",
     [f"{T}::test_pages_change_with_the_browsers_cross_page_transition"]),
    ("the new page pops in again", CSS,
     "::view-transition-old(root),\n::view-transition-new(root) {\n  animation-duration: 150ms;\n}\n",
     "::view-transition-old(root),\n::view-transition-new(root) {\n  animation-duration: 150ms;\n}\n\n"
     "::view-transition-new(root) {\n  animation: 240ms ease both ow-rise;\n  transform: translateY(8px);\n}\n",
     [f"{T}::test_the_swap_is_a_short_cross_fade_without_a_pop_in"]),
    ("the swap drags on", CSS,
     "  animation-duration: 150ms;\n", "  animation-duration: 600ms;\n",
     [f"{T}::test_the_swap_is_a_short_cross_fade_without_a_pop_in"]),
    ("the masthead fades with the page", CSS,
     "    view-transition-name: masthead;\n", "",
     [f"{T}::test_the_masthead_is_its_own_layer_and_stays_put"]),
    ("no bar in the masthead", "templates/base.html",
     '      <div class="c-loadbar" aria-hidden="true"></div>\n', "",
     [f"{T}::test_the_masthead_carries_a_loading_bar_and_its_script"]),
    ("the bar script is not loaded", "templates/base.html",
     "    <script src=\"{% static 'js/loading.js' %}\"></script>\n", "",
     [f"{T}::test_the_masthead_carries_a_loading_bar_and_its_script"]),
    ("the bar shows at once", CSS,
     "animation: ow-loadbar 15s ease-out 150ms both;",
     "animation: ow-loadbar 15s ease-out both;",
     [f"{T}::test_the_bar_waits_a_moment_then_creeps_without_finishing"]),
    ("the bar finishes on its own", CSS,
     "      transform: scaleX(0.95);\n", "      transform: scaleX(1);\n",
     [f"{T}::test_the_bar_waits_a_moment_then_creeps_without_finishing"]),
    ("the bar shows for new tabs", LOADING,
     "      link.target ||\n", "",
     [f"{T}::test_the_script_starts_the_bar_only_for_leaving_this_page"]),
    ("the bar shows for same-page anchors", LOADING,
     "      url.pathname !== window.location.pathname ||\n", "      true ||\n",
     [f"{T}::test_the_script_starts_the_bar_only_for_leaving_this_page"]),
    ("the bar shows for HTMX forms", LOADING,
     '      form.hasAttribute("hx-post") ||\n', "",
     [f"{T}::test_the_script_starts_the_bar_only_for_leaving_this_page"]),
    ("the bar never gives up", LOADING,
     "    timer = window.setTimeout(stop, 15000);\n", "",
     [f"{T}::test_the_bar_gives_up_and_clears_when_the_page_stays"]),
    ("the bar stays on after going back", LOADING,
     "    if (event.persisted) {\n      stop();\n    }\n", "",
     [f"{T}::test_the_bar_gives_up_and_clears_when_the_page_stays"]),
    ("downloads are not marked", "templates/me/security.html",
     'class="c-btn c-btn--secondary" download>', 'class="c-btn c-btn--secondary">',
     [f"{T}::test_downloads_are_marked_so_the_bar_skips_them"]),
    ("colour mode jumps", THEME,
     "    switchTo(choice);\n", "    apply(choice);\n    mark();\n",
     [f"{T}::test_changing_colour_mode_cross_fades"]),
    ("colour mode animates despite less motion", THEME,
     "    if (!document.startViewTransition || still) {\n",
     "    if (!document.startViewTransition) {\n",
     [f"{T}::test_asking_for_less_motion_switches_colour_mode_at_once"]),
    ("anchors always scroll smoothly", CSS,
     "  html {\n    scroll-behavior: smooth;\n  }\n}\n",
     "}\n\nhtml {\n  scroll-behavior: smooth;\n}\n",
     [f"{T}::test_anchor_links_scroll_smoothly_unless_less_motion_is_asked_for"]),
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
    assert run(every) == 0, "not green after restoring"
    print("restored and green;", "missed:", failed or "none")
    return 1 if failed else 0


sys.exit(main())
