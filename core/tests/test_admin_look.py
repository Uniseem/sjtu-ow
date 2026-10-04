"""Round 189: the admin in the site's own look, and a first page made for the
work (design 14.1, v6.67)."""

import re
from pathlib import Path

import pytest
from django.conf import settings
from django.core.management import call_command

from accounts.services import GROUP_SUBMITTER
from core.tests.test_admin_wording import _user

ADMIN_CSS = Path(settings.BASE_DIR) / "static" / "css" / "admin.css"
INPUT_CSS = Path(settings.BASE_DIR) / "assets" / "css" / "input.css"


@pytest.fixture
def site(db):
    call_command("init_site", verbosity=0)


def _block(css, opener):
    start = css.index(opener)
    return css[start : css.index("}", start)]


def _values(block, prefix):
    return dict(re.findall(rf"--{prefix}([a-z0-9-]+):\s*([^;]+);", block))


def test_the_admin_uses_the_sites_colour_values_light_and_dark():
    """The copies in admin.css must match input.css (13.2.1, 13.2.2)."""
    site_css = INPUT_CSS.read_text(encoding="utf-8")
    theme = site_css[site_css.index("@theme {") :]
    light = _values(theme[: theme.index("\n}\n")], "color-")
    dark_start = site_css.index("@variant dark {", site_css.index(":root {"))
    dark = _values(
        site_css[dark_start : site_css.index("\n    }\n", dark_start)], "color-"
    )

    admin = ADMIN_CSS.read_text(encoding="utf-8")
    admin_light = _values(
        _block(admin, ":root,\n.w-theme-light,\n.w-theme-system {"), "sj-"
    )
    admin_dark = _values(_block(admin, ".w-theme-dark {"), "sj-")
    admin_system = _values(_block(admin, "  .w-theme-system {"), "sj-")
    compared = 0
    for name, value in admin_light.items():
        if name in light:
            assert value.strip() == light[name].strip(), name
            compared += 1
    for name, value in admin_dark.items():
        if name in dark:
            assert value.strip() == dark[name].strip(), name
            assert admin_system[name] == value, name
            compared += 1
    assert compared >= 30


def test_wagtails_colours_point_at_the_tokens():
    admin = ADMIN_CSS.read_text(encoding="utf-8")
    mapping = _block(
        admin, ":root,\n.w-theme-light,\n.w-theme-dark,\n.w-theme-system {"
    )
    for wagtail, token in (
        ("surface-page", "bg"),
        ("surface-menus", "surface"),
        ("surface-button-default", "primary"),
        ("text-link-default", "primary-text"),
        ("surface-menu-item-active", "primary-soft"),
        ("secondary", "primary"),
        ("focus", "primary-text"),
    ):
        assert f"--w-color-{wagtail}: var(--sj-{token});" in mapping, wagtail
    assert "--w-font-sans: var(--sj-font);" in mapping


@pytest.mark.django_db
def test_every_admin_page_loads_the_look_and_the_sites_mark(site, client):
    """v7.0: the back office is the site's own page (app.css, b-brand); the
    Wagtail admin under /wagtail/ keeps admin.css and the site's mark."""
    client.force_login(_user("look189@example.com", superuser=True))
    for path in ("/admin/", "/admin/tournaments/", "/admin/images/"):
        html = client.get(path).content.decode()
        assert re.search(
            r'<link rel="stylesheet" href="/static/css/app[^"]*\.css', html
        ), path
        assert "/static/css/admin" not in html, path
        assert 'class="b-brand"' in html and "管理后台" in html, path
    for path in ("/wagtail/", "/wagtail/images/"):
        html = client.get(path).content.decode()
        assert re.search(
            r'<link rel="stylesheet" href="/static/css/admin[^"]*\.css">', html
        ), path
        assert 'class="a-brand"' in html and "底层后台" in html, path


@pytest.mark.django_db
def test_the_first_page_greets_and_offers_the_usual_work(site, client):
    from content.models import ArticleIndexPage

    owner = _user("owner189@example.com", superuser=True)
    # Something for Wagtail's own 「最近的编辑」 panel to show, were it kept.
    ArticleIndexPage.objects.get(slug="news").save_revision(user=owner, log_action=True)
    client.force_login(owner)
    html = client.get("/admin/").content.decode()
    assert f"你好，{owner.nickname}" in html and "超级管理员" in html
    actions = re.findall(r'class="c-btn[^"]*"[^>]*data-home-action>([^<]+)<', html)
    assert actions == ["写文章", "新建赛事", "新建内战", "打开网站"]
    # Nothing of Wagtail's dashboard (docs/admin.md 4.1).
    main = html.split('id="main"', 1)[1]
    assert 'class="w-' not in main and "最近的编辑" not in main
    for block in ("data-todo", "data-my-articles", "data-setup-list"):
        assert block in main, block


@pytest.mark.django_db
def test_each_role_gets_its_own_buttons(site, client):
    for number, (groups, wanted) in enumerate(
        (
            (("赛事管理员", GROUP_SUBMITTER), ["写文章", "新建赛事", "打开网站"]),
            (("内战管理员", GROUP_SUBMITTER), ["写文章", "新建内战", "打开网站"]),
            (("内容编辑",), ["写文章", "打开网站"]),
        )
    ):
        client.force_login(_user(f"buttons{number}-189@example.com", *groups))
        html = client.get("/admin/").content.decode()
        actions = re.findall(r"data-home-action>([^<]+)<", html)
        assert actions == wanted, groups
        assert "上线清单" not in html
        client.logout()


def test_admin_text_is_whole_pixels_with_yahei_before_pingfang():
    """Round 191 (用户：「字体可以做成模糊的了」): Wagtail's 85% body (13.6px)
    renders Chinese soft on Windows, and so does 苹方 when installed there."""
    admin = ADMIN_CSS.read_text(encoding="utf-8")
    assert re.search(r"\nbody \{\n  font-size: 14px;\n\}", admin)
    stack = re.search(r"--sj-font:([^;]+);", admin).group(1)
    assert stack.index('"Microsoft YaHei UI"') < stack.index('"PingFang SC"')
    mapping = _block(
        admin, ":root,\n.w-theme-light,\n.w-theme-dark,\n.w-theme-system {"
    )
    assert "--w-color-text-meta: var(--sj-fg-2);" in mapping
    assert "--w-color-text-label-menus-default: var(--sj-fg);" in mapping
