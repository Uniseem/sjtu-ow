"""Round 187: the masthead dropdowns close when you click elsewhere, and the
site has its own right-click menu that still lets the browser's through
where it matters (design 13.2.6, v6.65). Checked in a real browser for the
round; these keep the pieces from being dropped."""

import re
from pathlib import Path

import pytest
from django.conf import settings
from django.core.management import call_command

JS = Path(settings.BASE_DIR) / "static" / "js"
CONTEXT = (JS / "contextmenu.js").read_text(encoding="utf-8")
APP = (JS / "app.js").read_text(encoding="utf-8")


@pytest.fixture
def site(db):
    call_command("init_site", verbosity=0)


@pytest.mark.django_db
def test_every_front_page_loads_the_menu_script(site, client):
    html = client.get("/news/").content.decode()
    scripts = re.findall(r'<script src="([^"]+)"', html)
    names = [src.rsplit("/", 1)[-1].split(".")[0] for src in scripts]
    assert "contextmenu" in names
    assert names.index("app") < names.index("contextmenu")


@pytest.mark.django_db
def test_the_admin_keeps_the_browser_menu(site, client):
    from accounts.models import User

    owner = User.objects.create_superuser(email="root187@example.com", password=None)
    client.force_login(owner)
    assert "contextmenu" not in client.get("/admin/").content.decode()


def test_the_browser_menu_stays_where_it_is_needed():
    native = re.search(r'var NATIVE = "([^"]+)"', CONTEXT).group(1)
    places = ("input", "textarea", "select", "[contenteditable", "[data-native-")
    for place in places:
        assert place in native, place
    assert "event.shiftKey" in CONTEXT  # Shift + right click
    assert 'event.pointerType === "touch"' in CONTEXT  # a long press
    assert '"(pointer: fine)"' in CONTEXT  # phones skip the whole thing


def test_the_menu_is_built_without_markup_strings():
    assert "innerHTML" not in CONTEXT
    assert "insertAdjacentHTML" not in CONTEXT
    assert 'setAttribute("role", "menu")' in CONTEXT
    assert "按住 Shift 再右键：浏览器自带的菜单" in CONTEXT


def test_it_offers_what_the_design_lists():
    for label in (
        "在新标签页打开",
        "复制链接",
        "在新标签页打开图片",
        "复制图片地址",
        "复制",
        "在站内搜索",
        "后退",
        "前进",
        "刷新",
        "复制本页链接",
        "回到顶部",
        "已复制",
    ):
        assert f'"{label}' in CONTEXT, label


def test_it_closes_and_moves_by_keyboard():
    for key in ('"Escape"', '"ArrowDown"', '"ArrowUp"'):
        assert key in CONTEXT, key
    assert '"pointerdown"' in CONTEXT and '"scroll"' in CONTEXT


def test_the_dropdowns_close_on_outside_clicks_esc_and_each_other():
    assert 'var DROPDOWNS = "details.c-menu, details.c-theme, details.c-drawer";' in APP
    toggle = APP[APP.index('"toggle"') : APP.index('document.addEventListener("click"')]
    assert "closeDropdowns(target)" in toggle and toggle.rstrip().endswith("true\n  );")
    click = APP[APP.index('document.addEventListener("click"') :]
    assert "closeDropdowns(inside)" in click[: click.index("});")]
    escape = APP[APP.index('event.key !== "Escape"') :]
    assert "open.open = false" in escape and "summary.focus()" in escape


@pytest.mark.django_db
def test_the_style_guide_shows_the_context_menu(site, client):
    from accounts.models import User

    owner = User.objects.create_superuser(email="sg187@example.com", password=None)
    client.force_login(owner)
    html = client.get("/_styleguide/").content.decode()
    assert 'class="c-ctxmenu static' in html
    assert "c-ctxmenu__foot" in html
