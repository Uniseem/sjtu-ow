"""Moving between pages and modes without a hard cut or a flash (design
13.2.4, v6.4, round 106): a loading bar while the next page is on its way,
then a short cross-fade with no pop-in. The rules live in the stylesheet
source, base.html, loading.js and theme.js."""

import re
from pathlib import Path

from django.conf import settings

ROOT = Path(settings.BASE_DIR)
CSS = (ROOT / "assets" / "css" / "input.css").read_text(encoding="utf-8")
THEME = (ROOT / "static" / "js" / "theme.js").read_text(encoding="utf-8")
LOADING = (ROOT / "static" / "js" / "loading.js").read_text(encoding="utf-8")
BASE = (ROOT / "templates" / "base.html").read_text(encoding="utf-8")
CALM = "@media (prefers-reduced-motion: no-preference) {"
SWAP = "::view-transition-old(root),\n::view-transition-new(root) {"


def _block(text: str, opening: str) -> str:
    """The body of the first block that starts with `opening`."""
    start = text.index(opening)
    depth = 0
    for index in range(text.index("{", start), len(text)):
        if text[index] == "{":
            depth += 1
        elif text[index] == "}":
            depth -= 1
            if depth == 0:
                return text[text.index("{", start) + 1 : index]
    raise AssertionError(f"unclosed block: {opening}")


def _outside(text: str, opening: str) -> str:
    """`text` with that block cut out."""
    body = _block(text, opening)
    return text.replace(body, "", 1)


# --- the swap ------------------------------------------------------------------


def test_pages_change_with_the_browsers_cross_page_transition():
    calm = _block(CSS, CALM)
    assert re.search(r"@view-transition\s*\{\s*navigation:\s*auto;\s*\}", calm)
    # Nowhere else: with reduced motion asked for, pages switch at once.
    assert "@view-transition" not in _outside(CSS, CALM)


def test_the_swap_is_a_short_cross_fade_without_a_pop_in():
    """The first try faded the old page out to nothing and lifted the new
    one in: the page flashed and ended on a pop-in (user, round 106). Now
    only the duration changes; the browser's own blend keeps brightness."""
    swap = _block(CSS, SWAP)
    assert re.fullmatch(r"\s*animation-duration:\s*150ms;\s*", swap), swap
    rules = re.findall(r"::view-transition-[a-z-]+\(root\)[^{]*\{([^}]*)\}", CSS)
    for body in rules:
        assert "transform" not in body and "translate" not in body, body
        assert re.search(r"animation(-name)?\s*:", body) is None or (
            "animation-duration" in body and "animation:" not in body
        ), body


def test_the_masthead_is_its_own_layer_and_stays_put():
    masthead = _block(CSS, "  .c-masthead {")
    assert "view-transition-name: masthead;" in masthead


# --- waiting for the next page -----------------------------------------------


def test_the_masthead_carries_a_loading_bar_and_its_script():
    header = BASE[BASE.index('<header class="c-masthead">') : BASE.index("</header>")]
    assert '<div class="c-loadbar" aria-hidden="true"></div>' in header
    assert "{% static 'js/loading.js' %}" in BASE


def test_the_bar_waits_a_moment_then_creeps_without_finishing():
    bar = _block(CSS, "  .c-loadbar {")
    assert "position: absolute;" in bar and "bottom: 0;" in bar
    assert "transform: scaleX(0);" in bar
    assert "view-transition-name: loadbar;" in bar  # fades with the old page
    loading = _block(CSS, "  .is-loading .c-loadbar {")
    assert re.search(
        r"animation:\s*ow-loadbar\s+15s\s+ease-out\s+150ms\s+both;", loading
    )
    steps = re.findall(r"scaleX\(([\d.]+)\)", _block(CSS, "  @keyframes ow-loadbar {"))
    widths = [float(step) for step in steps]
    assert widths == sorted(widths) and widths[0] == 0
    assert widths[-1] < 1  # it only completes by the page going away


def test_the_script_starts_the_bar_only_for_leaving_this_page():
    click = _block(LOADING, 'document.addEventListener("click", function (event) {')
    for skipped in ("event.metaKey", "event.ctrlKey", "event.shiftKey", "event.altKey"):
        assert skipped in click, skipped
    for skipped in ("link.target", '"download"', '"data-no-loading"'):
        assert skipped in click, skipped
    leaves = _block(LOADING, "function leaves(url) {")
    assert "url.origin !== window.location.origin" in leaves
    assert "url.pathname !== window.location.pathname" in leaves
    submit = _block(LOADING, 'document.addEventListener("submit", function (event) {')
    for skipped in ('"hx-post"', '"hx-get"', "form.target", '"data-no-loading"'):
        assert skipped in submit, skipped


def test_the_bar_gives_up_and_clears_when_the_page_stays():
    start = _block(LOADING, "function start() {")
    assert "window.setTimeout(stop, 15000)" in start
    pageshow = _block(LOADING, 'window.addEventListener("pageshow", function (event) {')
    assert re.search(r"if \(event\.persisted\)\s*\{\s*stop\(\);", pageshow)


# --- the bar finishing on the next page (v6.6, round 108) ---------------------------

ARRIVAL = (ROOT / "static" / "js" / "arrival.js").read_text(encoding="utf-8")


def test_on_the_next_page_the_bar_runs_to_the_end_then_fades():
    """User: the bar should run smoothly, not linearly, to the end and then
    fade; it used to fade with the old page wherever it had stopped."""
    arriving = _block(CSS, "  .is-arriving .c-loadbar {")
    assert re.search(
        r"ow-loadbar-finish\s+300ms\s+cubic-bezier\(0\.2, 0, 0, 1\)\s+both", arriving
    )
    assert re.search(r"ow-loadbar-fade\s+250ms\s+ease\s+300ms\s+forwards", arriving)
    finish = _block(CSS, "  @keyframes ow-loadbar-finish {")
    assert "scaleX(var(--loadbar-from, 0.6))" in finish
    assert "scaleX(1)" in finish
    assert "opacity: 0;" in _block(CSS, "  @keyframes ow-loadbar-fade {")


def test_the_next_page_reads_where_the_bar_was_before_its_first_paint():
    head = BASE[: BASE.index("</head>")]
    assert "{% static 'js/arrival.js' %}" in head
    arrive = _block(ARRIVAL, "function arrive() {")
    assert "window.sessionStorage.removeItem(KEY)" in arrive  # read once
    assert "Date.now() - note.at > FRESH" in arrive
    assert 'root.style.setProperty("--loadbar-from"' in arrive
    assert 'root.classList.add("is-arriving")' in arrive
    assert "var FRESH = 20000;" in ARRIVAL
    # A prepared page looks when it is shown, not when it was prepared.
    assert re.search(
        r"if \(document\.prerendering\)\s*\{\s*document\.addEventListener\("
        r'"prerenderingchange", arrive',
        ARRIVAL,
    )


def test_only_a_bar_the_visitor_saw_is_finished():
    """A page that comes within the bar's delay never showed one, so the
    next page must not show a finishing bar out of nowhere."""
    key = re.search(r'var KEY = "([^"]+)";', LOADING).group(1)
    assert f'var KEY = "{key}";' in ARRIVAL
    delay = re.search(r"var SHOWN_AFTER = (\d+);", LOADING).group(1)
    assert f"ow-loadbar 15s ease-out {delay}ms both" in CSS
    start = _block(LOADING, "function start() {")
    assert re.search(
        r"shown = window\.setTimeout\(function \(\) \{\s*note\(\{ at: Date\.now\(\), "
        r"from: 0 \}\);\s*\}, SHOWN_AFTER\);",
        start,
    )
    assert "note(null);" in start  # an old note never reaches the next page
    assert 'root.classList.remove("is-arriving")' in start
    assert "note(null);" in _block(LOADING, "function stop() {")


def test_leaving_notes_where_the_bar_got_to():
    leaving = _block(LOADING, 'window.addEventListener("pagehide", function () {')
    assert re.search(
        r'if \(!root\.classList\.contains\("is-loading"\) \|\| !current\)', leaving
    )
    assert "current.from = progress();" in leaving
    assert "note(current);" in leaving


def test_downloads_are_marked_so_the_bar_skips_them():
    for name in ("delete.html", "security.html"):
        page = (ROOT / "templates" / "me" / name).read_text(encoding="utf-8")
        link = re.search(r"<a href=\"\{% url 'me_export' %\}\"[^>]*>", page)
        # Round 116: data-no-loading, not download (a download attribute saved
        # the rate-limit page as a file and lost its message).
        assert link and " data-no-loading" in link.group(0), name


# --- colour mode and anchors -------------------------------------------------


def test_changing_colour_mode_cross_fades():
    theme = _block(
        CSS,
        ":root.is-theme-switch::view-transition-old(root),\n"
        ":root.is-theme-switch::view-transition-new(root) {",
    )
    assert re.fullmatch(r"\s*animation-duration:\s*240ms;\s*", theme), theme
    switch = _block(THEME, "function switchTo(choice) {")
    assert "document.startViewTransition(" in switch
    assert 'root.classList.add("is-theme-switch")' in switch
    assert 'root.classList.remove("is-theme-switch")' in THEME
    # The menu goes through it.
    assert "switchTo(choice);" in _block(THEME, "function choose(event) {")


def test_asking_for_less_motion_switches_colour_mode_at_once():
    switch = _block(THEME, "function switchTo(choice) {")
    assert '"(prefers-reduced-motion: reduce)"' in switch
    assert re.search(
        r"if \(!document\.startViewTransition \|\| still\) \{\s*apply\(choice\);",
        switch,
    )


def test_anchor_links_scroll_smoothly_unless_less_motion_is_asked_for():
    assert "scroll-behavior: smooth;" in _block(CSS, CALM)
    assert "scroll-behavior: smooth" not in _outside(CSS, CALM)
