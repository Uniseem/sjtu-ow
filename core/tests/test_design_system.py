"""Design system (design 13.2): v2.0 in round 074, v3.0 in round 081, v4.0 in
round 086: tokens in two modes, chrome, style guide."""

import re
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

import pytest
from django.conf import settings
from django.contrib.auth.models import Permission
from django.template import Context, Template
from django.utils import timezone

from accounts.models import User
from content.models import RESERVED_CHILD_SLUGS
from content.tests.test_content import _tree
from core.fonts import services as font_services
from core.fonts.css import build_css, ordered_rules
from core.models import TypographyRule
from core.templatetags import ow

SHANGHAI = ZoneInfo("Asia/Shanghai")
INPUT_CSS = Path(settings.BASE_DIR) / "assets" / "css" / "input.css"
ERROR_CSS = Path(settings.BASE_DIR) / "static" / "css" / "error.css"
APP_CSS = Path(settings.BASE_DIR) / "static" / "css" / "app.css"
STATIC = Path(settings.BASE_DIR) / "static"


def _person(email, **extra):
    return User.objects.create_user(
        email=email,
        password="Correct-Horse-Battery-1",
        nickname=email.split("@")[0][:16],
        agreed_terms_at=timezone.now(),
        agreed_cross_border_at=timezone.now(),
        **extra,
    )


# --- fixed formats (13.2.4) ------------------------------------------------------


def test_dates_times_and_weekdays_have_one_format():
    moment = datetime(2026, 9, 4, 19, 5, tzinfo=SHANGHAI)
    assert ow.ow_date(moment) == "2026.09.04"
    assert ow.ow_md(moment) == "09.04"
    assert ow.ow_time(moment) == "19:05"
    assert ow.ow_weekday(moment) == "周五"
    assert ow.ow_weekday(moment.date().replace(day=6)) == "周日"


def test_times_are_shown_in_shanghai_time():
    utc = datetime(2026, 9, 4, 16, 30, tzinfo=ZoneInfo("UTC"))
    assert ow.ow_time(utc) == "00:30"
    assert ow.ow_md(utc) == "09.05"


def test_numbering_is_two_digits():
    assert [ow.ow_index(n) for n in (1, 9, 10, 12)] == ["01", "09", "10", "12"]
    assert ow.ow_index("x") == ""


def test_rank_labels_split_into_name_and_division():
    assert ow.rank_parts("钻石 3") == ("钻石", "3")
    assert ow.rank_parts("前 500") == ("前", "500")
    assert ow.rank_parts("") == ("", "")


def test_initial_is_the_first_character():
    assert ow.initial("夜航") == "夜"
    assert ow.initial("kairo") == "K"
    assert ow.initial("") == "?"


def test_rank_badge_template_sets_the_division_as_a_figure():
    html = Template(
        '{% include "components/rank_badge.html" with label="钻石 3" %}'
    ).render(Context({}))
    assert '钻石 <span class="c-rank__div">3</span>' in html
    unranked = Template('{% include "components/rank_badge.html" %}').render(
        Context({})
    )
    assert "c-rank--none" in unranked


# --- tokens (13.2.2) ------------------------------------------------------------


def test_only_our_palette_exists():
    """No stock Tailwind colours: templates cannot reach for bg-orange-500."""
    css = INPUT_CSS.read_text(encoding="utf-8")
    assert "--color-*: initial;" in css
    compiled = APP_CSS.read_text(encoding="utf-8")
    assert "--color-orange-500" not in compiled
    assert "--color-primary:#a4161a" in compiled.replace(" ", "")


HEX = r"--color-([a-z0-9-]+):\s*(#[0-9a-fA-F]{6})"
DARK_HEAD = "@media (prefers-color-scheme: dark) {"


def _light(css):
    """The @theme block: the light values (13.2.2)."""
    block = re.search(r"@theme \{(.*?)\n\}", css, flags=re.S).group(1)
    return dict(re.findall(HEX, block))


def _dark_block(css):
    block = css[css.index(DARK_HEAD) :]
    return block[: block.index("\n}\n")]


def _dark(css):
    """Light values overridden by the prefers-color-scheme: dark block."""
    return {**_light(css), **dict(re.findall(HEX, _dark_block(css)))}


def _tokens(css):
    return _light(css)


def test_error_css_uses_the_same_token_values():
    """error.css is hand-written (13.15); its colours must match input.css."""
    site = _tokens(INPUT_CSS.read_text(encoding="utf-8"))
    text = ERROR_CSS.read_text(encoding="utf-8")
    light_part = text[: text.index(DARK_HEAD)]
    errors = dict(re.findall(HEX, light_part))
    assert errors, "error.css defines no colour tokens"
    for name, value in errors.items():
        assert site.get(name, "").lower() == value.lower(), name
    # 089: the error pages follow the system too, with the site's dark values.
    site_dark = _dark(INPUT_CSS.read_text(encoding="utf-8"))
    dark = dict(re.findall(HEX, text[text.index(DARK_HEAD) :]))
    assert set(dark) == set(errors)
    for name, value in dark.items():
        assert site_dark[name].lower() == value.lower(), f"dark {name}"


def test_dark_mode_gives_every_palette_colour_a_dark_value():
    """13.2.1: both modes follow the system; a colour left out of the dark block
    would stay light on a dark page."""
    css = INPUT_CSS.read_text(encoding="utf-8")
    fixed = {"white", "black", "night", "night-2"}  # the same in both modes
    dark = set(dict(re.findall(HEX, _dark_block(css))))
    assert set(_light(css)) - fixed - dark == set()


# --- contrast (13.2.2, WCAG 2.1 AA) ----------------------------------------------


def _luminance(value):
    channels = [int(value[i : i + 2], 16) / 255 for i in (1, 3, 5)]
    linear = [
        c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4 for c in channels
    ]
    return 0.2126 * linear[0] + 0.7152 * linear[1] + 0.0722 * linear[2]


def _contrast(a, b):
    light, dark = sorted((_luminance(a), _luminance(b)), reverse=True)
    return (light + 0.05) / (dark + 0.05)


# The pairs in design 13.2.2: text needs 4.5:1, field borders 3:1.
GROUNDS = ("bg", "surface", "surface-2")
CONTRAST_PAIRS = [
    (("fg", "fg-2", "fg-3", "primary-text", "ok", "warn", "info"), GROUNDS, 4.5),
    (("white",), ("primary",), 4.5),
    (("on-primary-soft",), ("primary-soft",), 4.5),
    (("ok",), ("ok-soft",), 4.5),
    (("warn",), ("warn-soft",), 4.5),
    (("info",), ("info-soft",), 4.5),
    (("on-toast",), ("toast",), 4.5),
    (("white",), ("night", "night-2"), 4.5),
    (("control",), ("bg", "surface"), 3),
]


def test_the_contrast_helper_matches_known_values():
    assert round(_contrast("#000000", "#ffffff"), 2) == 21.0
    assert round(_contrast("#767676", "#ffffff"), 2) == 4.54


@pytest.mark.parametrize("mode", ["light", "dark"])
def test_text_and_field_colours_meet_wcag_aa(mode):
    """Round 079: ink-3 was 3.75:1 on the page and field borders about 2:1.
    Round 086: both modes are checked."""
    css = INPUT_CSS.read_text(encoding="utf-8")
    tokens = _light(css) if mode == "light" else _dark(css)
    failures = []
    for foregrounds, backgrounds, minimum in CONTRAST_PAIRS:
        for fg in foregrounds:
            for bg in backgrounds:
                ratio = _contrast(tokens[fg], tokens[bg])
                if ratio < minimum:
                    failures.append(f"{fg} on {bg}: {ratio:.2f} < {minimum}")
    assert failures == []


def test_the_style_guide_shows_every_colour_token_at_its_real_value():
    """The swatches repeat the hex values; 079 found ink-3 still at the old one."""
    from core.styleguide import COLOURS

    tokens = _tokens(INPUT_CSS.read_text(encoding="utf-8"))
    shown = {token: value.lower() for _label, token, _cls, value in COLOURS}
    expected = {k: v.lower() for k, v in tokens.items() if k not in ("white", "black")}
    assert shown == expected
    assert all(cls == f"bg-{token}" for _label, token, cls, _value in COLOURS)


def _block(css, head):
    start = css.index(head)
    return css[start : css.index("}", start)]


V3_NAMES = (
    "primary-deep",
    "primary-container",
    "tertiary-container",
    "surface-lowest",
    "surface-low",
    "surface-mid",
    "surface-high",
    "on-surface",
    "outline",
    "inverse-surface",
    "ok-container",
)


def test_the_v3_names_are_gone():
    """Round 089 finished M10: no v3 colour name, tone variable or glass
    variable is left in the stylesheet or the templates, so nothing can keep
    an old value in one of the two modes."""
    css = INPUT_CSS.read_text(encoding="utf-8")
    for name in V3_NAMES:
        assert f"--color-{name}" not in css, name
    assert "--tone-" not in css and "--glass-" not in css
    assert ".on-night" not in css and ".on-tonal" not in css
    names = "|".join(V3_NAMES) + "|panel|rule|fg-red"
    pattern = re.compile(rf"\b(?:bg|text|border|fill|stroke)-(?:{names})\b")
    offenders = [
        relative for relative, text in _front_templates() if pattern.search(text)
    ]
    assert offenders == []


def test_v4_draws_no_glass_and_no_washes():
    """13.2.1: no frosted panes, no gradient blobs; the only gradients are the
    scrims under words on a picture (13.2.5)."""
    css = INPUT_CSS.read_text(encoding="utf-8")
    assert "backdrop-filter" not in css
    # The one radial gradient is the dot inside a checked radio button.
    radials = [m.start() for m in re.finditer("radial-gradient", css)]
    assert len(radials) == 1
    assert 'input[type="radio"]:checked {' in css[radials[0] - 200 : radials[0]]
    gradients = re.findall(r"linear-gradient\(", css)
    assert len(gradients) == 3  # the scrims of c-hero, c-feature and c-stage


def test_no_text_is_smaller_than_14px():
    """13.2.3: the smallest size is 0.875rem (the user: 不要画蛇添足的说明小字)."""
    css = INPUT_CSS.read_text(encoding="utf-8")
    sizes = re.findall(r"font-size:\s*([0-9.]+)(rem|px)", css)
    small = [
        f"{value}{unit}"
        for value, unit in sizes
        if float(value) < (0.875 if unit == "rem" else 14)
    ]
    assert small == []
    tiny = re.compile(r"\btext-(?:xs|\[(?:0\.[0-7]|0\.8[0-6]|1[0-3]px)[^\]]*\])")
    assert [rel for rel, text in _front_templates() if tiny.search(text)] == []


def test_error_pages_carry_no_latin_label_or_small_print():
    """089: the error pages follow 13.2.1 too: no FORBIDDEN / MAINTENANCE line
    over the Chinese title, and no text under 14px in error.css."""
    base = Path(settings.BASE_DIR) / "templates" / "errors"
    for path in base.glob("*.html"):
        text = path.read_text(encoding="utf-8")
        assert "eyebrow" not in text, path.name
        for word in ("FORBIDDEN", "NOT FOUND", "MAINTENANCE", "SERVER ERROR"):
            assert word not in text, (path.name, word)
    css = ERROR_CSS.read_text(encoding="utf-8")
    sizes = [float(v) for v in re.findall(r"font-size:\s*([0-9.]+)rem", css)]
    assert min(sizes) >= 0.875


def test_colours_are_only_defined_as_tokens():
    """13.2.2: a colour written outside the token blocks escapes the contrast check."""
    css = INPUT_CSS.read_text(encoding="utf-8")
    outside = re.sub(r"@theme \{.*?\n\}", "", css, flags=re.S)
    outside = outside.replace(_dark_block(css), "")
    assert re.findall(r"#[0-9a-fA-F]{3,8}\b", outside) == []
    # Round 081: translucent colours too — mix a token instead of rgb().
    assert re.findall(r"\b(?:rgba?|hsla?)\(", outside) == []


@pytest.mark.parametrize(
    "head",
    [
        "\n  .c-input {",
        "\n  .c-check input {",
        "\n  .c-choice {",
        "\n  .c-drawer__search input {",
    ],
)
def test_form_fields_have_a_border_you_can_see(head):
    """WCAG 1.4.11: the edge that says "type here" needs 3:1, which the
    decorative line colour does not have (13.2.2)."""
    rule = _block(INPUT_CSS.read_text(encoding="utf-8"), head)
    assert "var(--tone-control)" in rule or "var(--color-control)" in rule


# --- --font-figure (13.2.4, 13.12.4) --------------------------------------------


@pytest.mark.django_db
def test_figures_use_system_din_until_a_numeric_font_is_chosen(tmp_path, settings):
    settings.MEDIA_ROOT = tmp_path
    font_services.ensure_typography_rules()
    assert "--font-figure" not in build_css(ordered_rules())

    family = font_services.create_family(
        name="数字体",
        source="upload",
        license_type="open_source",
    )
    from core.models import FontFace

    FontFace.objects.create(
        family=family,
        weight=600,
        status=FontFace.Status.READY,
        progress=100,
        slices=[
            {"path": "fonts/x/600-000.a.woff2", "unicode_range": "U+30", "bytes": 1}
        ],
        slice_count=1,
        total_bytes=1,
        glyph_count=1,
    )
    rule = TypographyRule.objects.get(region="numeric")
    rule.mode = TypographyRule.Mode.CUSTOM
    rule.family = family
    rule.weight = 600
    rule.save()
    css = build_css(ordered_rules())
    assert f'--font-figure: "{family.css_name}", var(--font-fallback);' in css


@pytest.mark.django_db
def test_button_region_rules_reach_the_system_button(tmp_path, settings):
    settings.MEDIA_ROOT = tmp_path
    font_services.ensure_typography_rules()
    rule = TypographyRule.objects.get(region="button")
    rule.size_rem = "1.0"
    rule.save()
    assert ".font-button, .c-btn {" in build_css(ordered_rules())


# --- chrome (13.3) --------------------------------------------------------------


@pytest.fixture
def home(db):
    _tree()


def test_masthead_marks_the_current_section(client, home):
    html = client.get("/news/").content.decode("utf-8")
    nav = html[html.index('class="c-nav') : html.index("</nav>")]
    assert '<a href="/news/" aria-current="page">资讯</a>' in nav
    assert nav.count('aria-current="page"') == 1


def test_phone_menu_is_a_details_element_that_marks_the_current_page(client, home):
    html = client.get("/news/").content.decode("utf-8")
    drawer = html[
        html.index('<details class="c-drawer') : html.index(
            "</details>", html.index('<details class="c-drawer')
        )
    ]
    assert "<summary" in drawer
    assert '<a href="/news/" aria-current="page">资讯</a>' in drawer
    assert drawer.count('aria-current="page"') == 1
    # v3.0 drops the numbers (13.3).
    assert "<span>01</span>" not in drawer


def test_every_page_carries_the_site_icon(client, home):
    for path in ("/", "/news/", "/accounts/login/"):
        html = client.get(path).content.decode("utf-8")
        assert re.search(
            r'<link rel="icon" href="/static/img/favicon[^"]*\.svg"', html
        ), path


def test_the_masthead_is_a_plain_bar_that_stays_put(client, home):
    """13.3 (v4.0): a solid bar, sticky, no glass, no capsule, no script."""
    html = client.get("/").content.decode("utf-8")
    assert '<header class="c-masthead">' in html
    assert "motion.js" not in html
    assert not (STATIC / "js" / "motion.js").exists()
    css = INPUT_CSS.read_text(encoding="utf-8")
    bar = _block(css, "\n  .c-masthead {")
    assert "position: sticky;" in bar
    assert "background-color: var(--color-surface);" in bar
    assert "backdrop-filter" not in bar
    assert "is-capsule" not in css and "is-hidden" not in css


def test_nothing_waits_for_a_script_to_appear(client, home):
    """13.2.4: no scroll reveals, count-ups or parallax; content is there as
    soon as the HTML is."""
    css = INPUT_CSS.read_text(encoding="utf-8")
    assert "data-reveal" not in css
    state = (STATIC / "js" / "state.js").read_text(encoding="utf-8")
    assert 'className += " js"' not in state
    html = client.get("/").content.decode("utf-8")
    for marker in ("data-reveal", "data-count-to", "data-parallax"):
        assert marker not in html, marker


def test_reduced_motion_also_drops_delays():
    """Round 082: under 「减少动态效果」 the duration went to zero but a delay
    stayed; the global rule clears both."""
    css = INPUT_CSS.read_text(encoding="utf-8")
    base = css[css.index("@layer base {") :]
    reduced = base[base.index("@media (prefers-reduced-motion: reduce)") :]
    reduced = reduced[: reduced.index("}\n  }")]
    assert "animation-delay: 0s !important;" in reduced
    assert "transition-delay: 0s !important;" in reduced


def test_homepage_columns_cannot_be_widened_by_their_content():
    """Round 082: a chip row widened the 资讯 column past a phone's width. Every
    homepage grid track is minmax(0, …)."""
    css = INPUT_CSS.read_text(encoding="utf-8")
    section = css[
        css.index("---- Homepage and the shared content blocks") : css.index(
            "---- Editorial pages"
        )
    ]
    tracks = re.findall(r"grid-template-columns:\s*([^;]+);", section)
    assert tracks
    for value in tracks:
        assert "minmax(0," in value, value


def test_the_emblem_file_is_clean_and_cropped():
    """13.2.8: the user-chosen emblem, cropped to a square, graphics only."""
    svg = (STATIC / "img" / "sjtu-emblem.svg").read_text(encoding="utf-8")
    box = re.search(r'viewBox="([\d.]+) ([\d.]+) ([\d.]+) ([\d.]+)"', svg)
    assert box, "no viewBox"
    width, height = float(box.group(3)), float(box.group(4))
    assert abs(width - height) < 0.1
    assert width < 300  # not the A4 page (595 × 842) it came on
    lowered = svg.lower()
    for bad in ("<script", "javascript:", "<foreignobject", "<image", 'href="http'):
        assert bad not in lowered, bad
    notices = (Path(settings.BASE_DIR) / "THIRD_PARTY_NOTICES.md").read_text(
        encoding="utf-8"
    )
    assert "static/img/sjtu-emblem.svg" in notices
    assert "weijianwen/SJTU-logo-banner" in notices


def test_footer_says_this_is_not_the_university_site(client, home):
    html = client.get("/").content.decode("utf-8")
    footer = html[html.index('<footer class="c-footer') :]
    assert "不是上海交通大学官方网站" in footer
    assert "与游戏开发商、运营商无关" in footer
    assert "游戏图片版权归暴雪娱乐所有" in footer


def test_signed_in_account_menu_needs_no_script(client, home):
    user = _person("menu@example.com")
    client.force_login(user)
    html = client.get("/news/").content.decode("utf-8")
    slot = html[
        html.index('id="slot-account"') : html.index(
            "</details>", html.index('id="slot-account"')
        )
    ]
    assert '<details class="c-menu">' in slot
    assert "个人中心" in slot and "退出" in slot


# --- style guide (13.2.7) -------------------------------------------------------


def test_style_guide_is_hidden_from_visitors_and_members(client, home):
    assert client.get("/_styleguide/").status_code == 404
    client.force_login(_person("member@example.com"))
    assert client.get("/_styleguide/").status_code == 404


def test_style_guide_opens_for_an_admin_who_is_not_a_superuser(client, home):
    editor = _person("editor@example.com")
    editor.user_permissions.add(
        Permission.objects.get(
            content_type__app_label="wagtailadmin", codename="access_admin"
        )
    )
    client.force_login(editor)
    response = client.get("/_styleguide/")
    assert response.status_code == 200
    html = response.content.decode("utf-8")
    for component in (
        "c-btn--primary",
        "c-stage",
        "c-meter",
        "c-status--live",
        "c-feature",
        "c-media",
        "c-date",
        "c-stats__list",
        "c-teams",
        "c-field",
        "c-prose",
    ):
        assert component in html, component


def test_style_guide_stays_out_of_robots_and_page_slugs(client, home):
    assert "_styleguide" in RESERVED_CHILD_SLUGS
    assert "Disallow: /_styleguide/" in client.get("/robots.txt").content.decode()
    assert "_styleguide" not in client.get("/sitemap.xml").content.decode()


# --- no daisyUI (13.2.7, round 077) -----------------------------------------------

# Wagtail admin templates never load the front-end stylesheet.
ADMIN_TEMPLATE_PARTS = (
    "/admin/",
    "core/templates/core/fonts",
    "core/templates/core/prerender",
    "moderation/templates",
    "templates/wagtail",
    "content/templates/content/admin",
)
DAISY_CLASS = re.compile(
    r"^(btn(-.+)?|badge(-.+)?|card(-.+)?|alert(-.+)?|menu(-.+)?|tabs?(-.+)?"
    r"|join(-item)?|toast(-.+)?|hero(-.+)?|link(-primary|-hover)?"
    r"|label(-text(-alt)?)?|form-control|input(-bordered|-sm|-xs)?"
    r"|select(-bordered)?|textarea(-bordered)?|checkbox|radio|toggle"
    r"|drawer(-.+)?|divider|stat(-.+)?|collapse(-.+)?|loading(-.+)?|rounded-box"
    r"|(bg|text|border|divide)-(base-\d00|base-content|primary|secondary|accent"
    r"|neutral|info|success|warning|error)(-content)?(/\d+)?)$"
)


def _front_templates():
    base = Path(settings.BASE_DIR)
    for root in [base / "templates", *sorted(base.glob("*/templates"))]:
        for path in root.rglob("*.html"):
            relative = path.relative_to(base).as_posix()
            if not any(part in relative for part in ADMIN_TEMPLATE_PARTS):
                yield relative, path.read_text(encoding="utf-8")


def test_front_end_templates_use_no_daisyui_classes():
    offenders = []
    for relative, text in _front_templates():
        for match in re.finditer(r'class="([^"]*)"', text):
            for token in match.group(1).split():
                if DAISY_CLASS.match(token.split(":")[-1]):
                    offenders.append(f"{relative}: {token}")
    assert offenders == []


def test_the_stylesheet_no_longer_loads_daisyui():
    css = INPUT_CSS.read_text(encoding="utf-8")
    assert "daisyui" not in css
    compiled = APP_CSS.read_text(encoding="utf-8")
    assert ".btn{" not in compiled.replace(" ", "")
    assert "--color-base-100" not in compiled


def test_the_account_centre_is_not_marked_as_a_section(client, home):
    """/me/teams/ and /me/registrations/ contain /teams/ and /registrations/."""
    client.force_login(_person("nav-me@example.com"))
    for path in ("/me/teams/", "/me/registrations/", "/me/scrims/"):
        html = client.get(path).content.decode("utf-8")
        nav = html[html.index('class="c-nav') : html.index("</nav>")]
        assert 'aria-current="page"' not in nav, path
    html = client.get("/teams/").content.decode("utf-8")
    nav = html[html.index('class="c-nav') : html.index("</nav>")]
    assert '<a href="/teams/" aria-current="page">战队</a>' in nav


# --- account centre (13.5, round 077) ---------------------------------------------


def test_the_account_menu_has_icons_and_marks_the_current_page(client, home):
    """v3.0 (round 085): each item carries an icon; the 01–07 numbers are gone."""
    from accounts.views import ME_NAV

    client.force_login(_person("menu-me@example.com"))
    html = client.get("/me/game-accounts/").content.decode("utf-8")
    menu = html[
        html.index('<ul class="c-sidenav') : html.index(
            "</ul>", html.index('<ul class="c-sidenav')
        )
    ]
    assert menu.count('class="size-5 c-sidenav__icon"') == len(ME_NAV) == 7
    assert "c-sidenav__index" not in menu
    assert len({icon for *_rest, icon in ME_NAV}) == 7  # one icon each
    current = menu[menu.index('aria-current="page"') :]
    assert "游戏 ID 与段位</a>" in current[: current.index("</li>")]
    assert menu.count('aria-current="page"') == 1


def test_the_account_centre_head_shows_who_you_are(client, home):
    client.force_login(_person("whoami@example.com"))
    html = client.get("/me/").content.decode("utf-8")
    head = html[
        html.index('<header class="c-pagehead">') : html.index(
            "</header>", html.index('<header class="c-pagehead">')
        )
    ]
    assert "ACCOUNT" not in head
    assert re.search(
        r'<span class="c-avatar c-avatar--sm" aria-hidden="true">[wW]</span>', head
    )
    assert "whoami</span>" in head


def test_sign_in_is_a_card_beside_what_an_account_is_for(client, home):
    html = client.get("/accounts/login/").content.decode("utf-8")
    main = html[html.index("<main") : html.index("</main>")]
    assert '<section class="c-auth">' in main
    assert "ACCOUNT" not in main
    why = main[main.index('<aside class="c-why') : main.index("</aside>")]
    assert why.count('class="c-why__icon') == 3
    assert "border-fg" not in main
    card = _block(INPUT_CSS.read_text(encoding="utf-8"), "  .c-auth {")
    assert "border: 1px solid var(--color-line);" in card
    assert "border-radius: var(--radius-sm);" in card


@pytest.mark.parametrize(
    "path",
    [
        "templates/account/layout.html",
        "templates/me/base.html",
        "teams/templates/teams/apply.html",
        "teams/templates/teams/create.html",
        "teams/templates/teams/manage.html",
        "tournaments/templates/tournaments/individual_signup.html",
        "tournaments/templates/tournaments/register.html",
        "tournaments/templates/tournaments/registration_detail.html",
    ],
)
def test_form_pages_carry_no_latin_eyebrow(path):
    text = (Path(settings.BASE_DIR) / path).read_text(encoding="utf-8")
    assert "c-eyebrow" not in text


def test_no_front_template_draws_v2_heavy_rules():
    """v2.0 separated things with 2px ink rules; v3.0 uses cards (round 085)."""
    offenders = []
    for relative, text in _front_templates():
        for token in ("border-fg", "border-t-2", "border-b-2", "border-y-2"):
            if token in text:
                offenders.append(f"{relative}: {token}")
    assert offenders == []


def test_the_phone_tab_strip_opens_on_the_current_page(client, home):
    """Round 078: on a phone the account centre's tabs scroll sideways and
    「账号安全」 opened hidden past the right edge. app.js scrolls every
    c-tabs strip to its aria-current item (checked in a real browser in the
    078 report); this pins the markup and the script to each other."""
    client.force_login(_person("tabs-me@example.com"))
    html = client.get("/me/security/").content.decode("utf-8")
    start = html.index('<div class="c-tabs')
    strip = html[start : html.index("</div>", start)]
    assert strip.count('aria-current="page"') == 1
    assert '<a href="/me/security/" aria-current="page">' in strip

    script = (Path(settings.BASE_DIR) / "static" / "js" / "app.js").read_text()
    assert 'document.querySelectorAll(".c-tabs")' in script
    assert 'querySelector(\'[aria-current="page"]' in script
    assert ".scrollLeft = current.offsetLeft" in script


def test_a_game_id_panel_sets_each_rank_as_a_figure(client, home):
    user = _person("ranks@example.com")
    user.game_accounts.create(battletag="Genji#51234", rank_tank=22, rank_support=40)
    client.force_login(user)
    html = client.get("/me/game-accounts/").content.decode("utf-8")
    panel = html[html.index("data-game-account") :]
    assert '钻石 <span class="c-rank__div">3</span>' in panel
    assert '前 <span class="c-rank__div">500</span>' in panel
    assert "c-rank--none" in panel  # damage is unranked


@pytest.mark.parametrize(
    "status, shape",
    [
        ("approved", "c-status--ok"),
        ("pending", "c-status--warn"),
        ("rejected", "c-status--rejected"),
        ("withdrawn", "c-status--off"),
    ],
)
def test_registration_status_has_its_own_shape(status, shape):
    class Registration:
        def __init__(self):
            self.status = status

        def get_status_display(self):
            return status

    html = Template('{% include "components/registration_status.html" %}').render(
        Context({"registration": Registration()})
    )
    assert shape in html
