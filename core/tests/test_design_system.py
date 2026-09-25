"""Design system v2.0 (design 13.2, round 074): tokens, chrome, style guide."""

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


def test_slot_cells_fill_then_empty_then_overflow():
    assert ow.slot_cells(3, 5) == ["on", "on", "on", "off", "off"]
    assert ow.slot_cells(6, 5) == ["on"] * 5 + ["over"]
    assert ow.slot_cells(0, 2) == ["off", "off"]


def test_slot_cells_give_way_to_a_bar_past_24():
    assert ow.slot_cells(10, 24) != []
    assert ow.slot_cells(10, 25) == []
    assert ow.slot_cells(25, 20) == []
    assert ow.percent_of(31, 48) == 65
    assert ow.percent_of(60, 48) == 100
    assert ow.percent_of(3, 0) == 0


def test_rank_labels_split_into_name_and_division():
    assert ow.rank_parts("钻石 3") == ("钻石", "3")
    assert ow.rank_parts("前 500") == ("前", "500")
    assert ow.rank_parts("") == ("", "")


def test_initial_is_the_first_character():
    assert ow.initial("夜航") == "夜"
    assert ow.initial("kairo") == "K"
    assert ow.initial("") == "?"


def test_slot_meter_template_draws_cells_and_says_the_count():
    html = Template(
        '{% include "components/slots.html" with taken=2 capacity=3 unit="人" %}'
    ).render(Context({}))
    assert html.count('<i class="is-on">') == 2
    assert html.count("<i></i>") == 1
    assert "已报 </span>2<span> / 3</span>" in html


def test_rank_badge_template_sets_the_division_as_a_figure():
    html = Template(
        '{% include "components/rank_badge.html" with label="钻石 3" %}'
    ).render(Context({}))
    assert '钻石 <span class="c-rank__div">3</span>' in html
    unranked = Template('{% include "components/rank_badge.html" %}').render(
        Context({})
    )
    assert "c-rank--none" in unranked


# --- tokens (13.2.3) ------------------------------------------------------------


def test_only_our_palette_exists():
    """No stock Tailwind colours: templates cannot reach for bg-orange-500."""
    css = INPUT_CSS.read_text(encoding="utf-8")
    assert "--color-*: initial;" in css
    compiled = APP_CSS.read_text(encoding="utf-8")
    assert "--color-orange-500" not in compiled
    assert "--color-red:#b2141a" in compiled.replace(" ", "")


def _tokens(css):
    return dict(re.findall(r"--color-([a-z0-9-]+):\s*(#[0-9a-fA-F]{6})", css))


def test_error_css_uses_the_same_token_values():
    """error.css is hand-written (13.15); its colours must match input.css."""
    site = _tokens(INPUT_CSS.read_text(encoding="utf-8"))
    errors = _tokens(ERROR_CSS.read_text(encoding="utf-8"))
    assert errors, "error.css defines no colour tokens"
    for name, value in errors.items():
        assert site.get(name, "").lower() == value.lower(), name


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


def test_phone_menu_is_a_details_element_with_numbered_items(client, home):
    html = client.get("/").content.decode("utf-8")
    drawer = html[
        html.index('<details class="c-drawer') : html.index(
            "</details>", html.index('<details class="c-drawer')
        )
    ]
    assert "<summary" in drawer
    assert "<span>01</span>首页" in drawer
    assert "<span>06</span>成员" in drawer


def test_every_page_carries_the_site_icon(client, home):
    for path in ("/", "/news/", "/accounts/login/"):
        html = client.get(path).content.decode("utf-8")
        assert re.search(
            r'<link rel="icon" href="/static/img/favicon[^"]*\.svg"', html
        ), path


def test_footer_says_this_is_not_the_university_site(client, home):
    html = client.get("/").content.decode("utf-8")
    footer = html[html.index('<footer class="c-footer') :]
    assert "不是上海交通大学官方网站" in footer
    assert "与游戏开发商、运营商无关" in footer


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
        "c-ticket",
        "c-slots",
        "c-status--live",
        "c-daystrip",
        "c-field",
        "c-prose",
    ):
        assert component in html, component


def test_style_guide_stays_out_of_robots_and_page_slugs(client, home):
    assert "_styleguide" in RESERVED_CHILD_SLUGS
    assert "Disallow: /_styleguide/" in client.get("/robots.txt").content.decode()
    assert "_styleguide" not in client.get("/sitemap.xml").content.decode()
