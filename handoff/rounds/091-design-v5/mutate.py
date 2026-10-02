"""Round 091: break each new rule once and check its test goes red (AGENTS.md
rule 7). Runs the tests first and stops if they are not green (083).

uv run python handoff/rounds/091-design-v5/mutate.py
"""

import os
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
PY = sys.executable
ENV = {**os.environ, "PYTHONUTF8": "1"}

CM = "core/tests/test_colour_modes.py"
DS = "core/tests/test_design_system.py"
CP = "core/tests/test_cover_placeholders.py"
HS = "content/tests/test_home_sections.py"

MUTATIONS = [
    ("night band covers the masthead again", "assets/css/input.css",
     "  .c-stage:not(.c-stage--plain),\n  .c-footer {",
     "  .c-masthead,\n  .c-stage:not(.c-stage--plain),\n  .c-footer {",
     [f"{CM}::test_only_the_footer_and_banners_with_a_cover_stay_night"]),
    ("night scene hidden in dark mode too", "assets/css/input.css",
     "    @variant dark {\n      display: block;\n    }",
     "    @variant dark {\n      display: none;\n    }",
     [f"{CM}::test_each_scene_shows_only_in_its_own_mode"]),
    ("a rule reads the system mode directly", "assets/css/input.css",
     "  .c-scene--light {",
     "  @media (prefers-color-scheme: dark) {\n    .c-x {\n      opacity: 1;\n    }\n  }\n\n  .c-scene--light {",
     [f"{DS}::test_the_dark_values_apply_when_chosen_or_when_the_system_is_dark"]),
    ("display orange too bright on white", "assets/css/input.css",
     "  --color-accent-display: #cc6f00;", "  --color-accent-display: #e8890c;",
     [f"{DS}::test_text_and_field_colours_meet_wcag_aa"]),
    ("hero veiled in night, not the page ground", "assets/css/input.css",
     "color-mix(in oklab, var(--color-bg) 62%, transparent) 50%,",
     "color-mix(in oklab, var(--color-night) 62%, transparent) 50%,",
     [f"{CM}::test_the_hero_and_section_heads_are_veiled_in_the_page_ground"]),
    ("emblem drawn opaque white", "assets/css/input.css",
     "    background-color: color-mix(in oklab, var(--color-fg) 20%, transparent);",
     "    background-color: var(--color-white);",
     [f"{CM}::test_the_emblem_is_see_through_in_the_mode_s_colours_and_its_gear_turns"]),
    ("theme script loads late", "templates/base.html",
     "    <script src=\"{% static 'js/theme.js' %}\"></script>\n    {% tailwind_css %}",
     "    {% tailwind_css %}\n    {% block theme_late %}{% endblock %}",
     [f"{CM}::test_the_mode_is_set_before_the_page_paints"]),
    ("theme menu shown without the script", "templates/base.html",
     '<details class="c-theme max-sm:hidden" data-theme-menu hidden>',
     '<details class="c-theme max-sm:hidden" data-theme-menu>',
     [f"{CM}::test_the_masthead_offers_three_modes_once_the_script_runs"]),
    ("storage write not guarded", "static/js/theme.js",
     "    try {\n      if (choice === \"system\") {",
     "    {\n      if (choice === \"system\") {",
     [f"{CM}::test_the_script_keeps_a_pick_and_forgets_it_for_the_system"]),
    ("pictures ignore reduced motion", "core/placeholders.py",
     'STILL = "@media (prefers-reduced-motion:reduce){*{animation:none!important}}"',
     'STILL = ""',
     [f"{CP}::test_every_picture_moves_and_stands_still_under_reduced_motion",
      f"{CP}::test_the_committed_pictures_are_what_the_code_draws"]),
    ("day palette with a different list length", "core/placeholders.py",
     '"windows": ["#dfe9f3", "#cfe0ef", "#f3e8cf"],',
     '"windows": ["#dfe9f3", "#cfe0ef"],',
     [f"{CP}::test_the_committed_pictures_are_what_the_code_draws"]),
    ("only the night scene behind a section head", "core/templatetags/ow.py",
     'for mode in ("light", "dark")\n',
     'for mode in ("dark",)\n',
     [f"{CM}::test_a_section_head_has_its_scene_by_day_and_night",
      f"{HS}::test_the_hero_shows_the_uploaded_picture_or_else_its_scene_by_day_and_night"]),
    ("settings loaded again instead of from the request", "core/templatetags/ow.py",
     'site = SiteSettings.load(request_or_site=context.get("request"))',
     "site = SiteSettings.load()",
     ["teams/tests/test_teams.py::test_team_list_does_not_run_a_query_per_team"]),
    ("a section banner refreshes nothing", "core/signals.py",
     '    "banner_teams_id": ("/teams/", "team_index"),\n', "",
     ["core/tests/test_regeneration_events.py::test_a_section_banner_refreshes_its_section_page"]),
    ("the news banner refreshes nothing", "core/signals.py",
     'prerender.request_page(url, kind="article_index")', 'pass',
     ["core/tests/test_regeneration_events.py::test_a_section_banner_refreshes_its_section_page"]),
    ("figures back under the hero", "content/templates/content/home_page.html",
     '    <div class="l-container c-hero__foot">',
     '  </section>\n  <section>\n    <div class="l-container c-hero__foot">',
     [f"{HS}::test_the_figures_close_the_hero"]),
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
            for cache in ROOT.glob(rel.rsplit("/", 1)[0] + "/__pycache__/*.pyc"):
                cache.unlink()
    assert run(every) == 0, "not green after restoring"
    print("restored and green;", "missed:", failed or "none")
    return 1 if failed else 0


sys.exit(main())
