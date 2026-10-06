"""Caching, compression and preparing the next page (design 13.10, 13.13.2,
v6.3, round 105): what a visitor far from the server waits for."""

import json
import re
from pathlib import Path

import pytest
from django.conf import settings
from django.core.management import call_command
from django.utils.csp import build_policy

DEPLOY = Path(settings.BASE_DIR) / "deploy"
CADDYFILE = DEPLOY / "Caddyfile"


def _caddy() -> str:
    """The Caddyfile without comments."""
    lines = CADDYFILE.read_text(encoding="utf-8").splitlines()
    return "\n".join(line for line in lines if not line.lstrip().startswith("#"))


def _block(text: str, opening: str) -> str:
    """The body of the block that starts with `opening` (up to its `{`)."""
    start = text.index(opening)
    depth = 0
    for index in range(text.index("{", start), len(text)):
        if text[index] == "{":
            depth += 1
        elif text[index] == "}":
            depth -= 1
            if depth == 0:
                return text[start : index + 1]
    raise AssertionError(f"unclosed block: {opening}")


# --- Caddy ---------------------------------------------------------------------


def test_prerendered_pages_carry_the_same_policy_as_django():
    """Round 105: pages Caddy served itself had no CSP at all, while the same
    page through Django had one. Most front-end views are prerendered."""
    caddy = _caddy()
    security = _block(caddy, "(page_security)")
    policy = re.search(r'Content-Security-Policy "([^"]+)"', security)
    assert policy, "no Content-Security-Policy in (page_security)"
    assert policy.group(1) == build_policy(settings.SECURE_CSP)
    assert f'X-Frame-Options "{settings.X_FRAME_OPTIONS}"' in security
    assert 'X-Content-Type-Options "nosniff"' in security
    assert f'Referrer-Policy "{settings.SECURE_REFERRER_POLICY}"' in security
    assert (
        f'Cross-Origin-Opener-Policy "{settings.SECURE_CROSS_ORIGIN_OPENER_POLICY}"'
        in security
    )
    assert "import page_security" in _block(caddy, "handle @prerendered")


def test_caddy_does_not_serve_precompressed_files():
    """Caddy 2.10's precompressed answers 206 Partial Content to requests
    that asked for no range; compression happens on the fly instead."""
    caddy = _caddy()
    assert "precompressed" not in caddy
    assert re.search(r"^\s*encode\s+zstd\s+gzip\s*$", caddy, re.M)


def test_thumbnails_are_kept_a_year_and_other_uploads_a_day():
    """Design 13.10: thumbnails were meant to be immutable but had no
    Cache-Control at all, so each visit re-checked every face."""
    caddy = _caddy()
    images = _block(caddy, "handle /media/images/*")
    assert 'Cache-Control "public, max-age=31536000, immutable"' in images
    uploads = _block(caddy, "handle /media/* {")
    assert 'Cache-Control "public, max-age=86400"' in uploads


def _django_hsts() -> str:
    """The Strict-Transport-Security header Django sends in production, from
    the values in settings/prod.py run through Django's own middleware."""
    import ast

    from django.http import HttpResponse
    from django.middleware.security import SecurityMiddleware
    from django.test import RequestFactory, override_settings

    prod = Path(settings.BASE_DIR) / "sjtu_ow" / "settings" / "prod.py"
    wanted = {}
    for node in ast.parse(prod.read_text(encoding="utf-8")).body:
        if isinstance(node, ast.Assign) and isinstance(node.targets[0], ast.Name):
            name = node.targets[0].id
            if name.startswith("SECURE_HSTS_"):
                wanted[name] = ast.literal_eval(node.value)
    assert set(wanted) == {
        "SECURE_HSTS_SECONDS",
        "SECURE_HSTS_INCLUDE_SUBDOMAINS",
        "SECURE_HSTS_PRELOAD",
    }
    with override_settings(**wanted):
        middleware = SecurityMiddleware(lambda request: HttpResponse())
        response = middleware(RequestFactory().get("/", secure=True))
    return response["Strict-Transport-Security"]


# Every way Caddy answers from disk, by the line that opens its block.
CADDY_FILE_ROUTES = (
    "(page_security)",
    "handle @hashed_static",
    "handle /static/*",
    "handle @hashed_fonts",
    "handle /media/images/*",
    "handle /media/* {",
)


def test_what_caddy_serves_itself_carries_django_s_hsts():
    """Design 15.2 (v7.18, 210 review C6): only Django's own pages sent HSTS,
    and the first visit nearly always lands on the prerendered homepage."""
    caddy = _caddy()
    value = re.search(
        r'header Strict-Transport-Security "([^"]+)"',
        _block(caddy, "(transport_security)"),
    )
    assert value, "no Strict-Transport-Security in (transport_security)"
    assert value.group(1) == _django_hsts()
    for opening in CADDY_FILE_ROUTES:
        assert "import transport_security" in _block(caddy, opening), opening
    # Django sends its own; the header must not be doubled on its routes.
    assert "transport_security" not in _block(caddy, "(django)")
    assert caddy.count("Strict-Transport-Security") == 1


def test_uploaded_font_originals_are_not_served():
    """Design 15.2 (v7.18, 210 review C4): originals live under
    media/fonts/<id>/original/ and `handle /media/*` served them to anyone.
    Only the hashed stylesheet and the slices are public."""
    caddy = _caddy()
    fonts = _block(caddy, "handle /media/fonts/*")
    assert "respond 404" in fonts
    assert "file_server" not in fonts
    # Before the catch-all for uploads, after the public font files.
    assert (
        caddy.index("handle @hashed_fonts")
        < caddy.index("handle /media/fonts/*")
        < caddy.index("handle /media/* {")
    )
    public = re.search(r"@hashed_fonts path_regexp hashed_fonts (\S+)", caddy)
    pattern = re.compile(public.group(1))
    assert pattern.match("/media/fonts/css/fonts.0123456789ab.css")
    assert pattern.match("/media/fonts/3/latin.0123456789ab.woff2")
    assert not pattern.match("/media/fonts/3/original/Source.woff2")
    assert not pattern.match("/media/fonts/3/original/Source.otf")


# --- preparing the next page -------------------------------------------------------


def _rules(html: str) -> dict:
    found = re.findall(r'<script type="speculationrules">(.*?)</script>', html, re.S)
    assert len(found) == 1, found
    return json.loads(found[0])


@pytest.fixture
def site(db):
    call_command("init_site", verbosity=0)


@pytest.mark.django_db
def test_pages_ask_the_browser_to_prepare_public_links(client, site):
    rules = _rules(client.get("/").content.decode())
    (rule,) = rules["prerender"]
    assert rule["eagerness"] == "moderate"
    conditions = rule["where"]["and"]
    assert {"href_matches": "/*"} in conditions
    excluded = next(
        c["not"]["href_matches"]
        for c in conditions
        if "href_matches" in c.get("not", {})
    )
    for prefix in (
        "/admin/*",
        "/wagtail/*",
        "/accounts/*",
        "/me/*",
        "/_fragments/*",
        "/_styleguide/*",
    ):
        assert prefix in excluded, prefix
    selector = next(
        c["not"]["selector_matches"]
        for c in conditions
        if "selector_matches" in c.get("not", {})
    )
    for marker in ("[download]", "[target]", "[data-no-prerender]"):
        assert marker in selector, marker


@pytest.mark.django_db
def test_prerendered_files_carry_the_rules_too(settings, tmp_path, site):
    from core import prerender

    settings.PRERENDER_ENABLED = True
    settings.PRERENDER_ROOT = tmp_path
    prerender.generate("/")
    html = (tmp_path / "index.html").read_text(encoding="utf-8")
    assert _rules(html)["prerender"]


def test_a_prepared_page_waits_to_be_shown_before_asking_who_is_signed_in():
    """Design 13.13.3 (v6.3): a page prepared ahead of a click asks for the
    sign-in state and the flash message only once it is on screen."""
    script = (Path(settings.BASE_DIR) / "static" / "js" / "state.js").read_text(
        encoding="utf-8"
    )
    assert re.search(r"if \(d\.prerendering\)\s*\{", script)
    assert 'addEventListener("prerenderingchange", start' in script
