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
