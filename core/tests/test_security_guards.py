"""Security checks that had no test until round 059's guard sweep."""

import os
import subprocess
import sys

import pytest
from django.conf import settings as django_settings

from core import prerender
from core.net import UnsafeUrl, assert_public_https_url
from core.prerender import PrerenderError, normalize_path

# --- SSRF guard (core/net.py) ---------------------------------------------------
# A literal public IP needs no DNS, so without the scheme checks nothing else
# would refuse these. The older download test passed only because the network
# request itself failed.


def test_http_is_refused():
    with pytest.raises(UnsafeUrl, match="https"):
        assert_public_https_url("http://93.184.216.34/font.ttf")


def test_other_schemes_are_refused():
    with pytest.raises(UnsafeUrl, match="https"):
        assert_public_https_url("ftp://93.184.216.34/font.ttf")


def test_a_url_without_a_host_is_refused():
    with pytest.raises(UnsafeUrl, match="主机名"):
        assert_public_https_url("https:///font.ttf")


# --- prerender paths and gates ----------------------------------------------------


@pytest.mark.parametrize(
    "path, reason",
    [
        ("news/", "以 / 开头"),
        ("/news/?page=2", "查询参数"),
        ("/news/../etc/", "不合法"),
    ],
)
def test_a_bad_prerender_path_is_refused(path, reason):
    """The path becomes a file under PRERENDER_ROOT; '..' would climb out."""
    with pytest.raises(PrerenderError, match=reason):
        normalize_path(path)


def _serve(monkeypatch, response):
    from django.test import Client

    monkeypatch.setattr(Client, "get", lambda self, path, **kwargs: response)


@pytest.mark.django_db
def test_an_error_page_is_never_frozen(monkeypatch):
    from django.http import HttpResponse

    page = HttpResponse("<html><body>出错了</body></html>", status=500)
    page["Content-Type"] = "text/html; charset=utf-8"
    _serve(monkeypatch, page)
    with pytest.raises(PrerenderError, match="500"):
        prerender.render_html("/")


@pytest.mark.django_db
def test_something_that_is_not_html_is_never_frozen(monkeypatch):
    from django.http import JsonResponse

    _serve(monkeypatch, JsonResponse({"ok": True}))
    with pytest.raises(PrerenderError, match="不是 HTML"):
        prerender.render_html("/")


# --- production settings refuse to start --------------------------------------------


def _import_prod(**overrides):
    env = {
        **os.environ,
        "DJANGO_SECRET_KEY": "guard-test-secret-key-not-used-anywhere-else",
        "SITE_URL": "https://example.com",
        "DJANGO_ALLOWED_HOSTS": "example.com",
        "DJANGO_CSRF_TRUSTED_ORIGINS": "https://example.com",
        "FIELD_ENCRYPTION_KEY": "guard-test-field-key",
    }
    env.update(overrides)
    # A fresh interpreter: a failed reload in this one would leave the module
    # half executed for later tests.
    return subprocess.run(
        [sys.executable, "-c", "import sjtu_ow.settings.prod"],
        cwd=django_settings.BASE_DIR,
        env=env,
        capture_output=True,
        text=True,
        timeout=60,
    )


def test_the_production_settings_start_when_complete():
    assert _import_prod().returncode == 0


@pytest.mark.parametrize(
    "overrides, message",
    [
        ({"DJANGO_ALLOWED_HOSTS": ""}, "DJANGO_ALLOWED_HOSTS"),
        ({"DJANGO_CSRF_TRUSTED_ORIGINS": ""}, "DJANGO_CSRF_TRUSTED_ORIGINS"),
        ({"FIELD_ENCRYPTION_KEY": ""}, "FIELD_ENCRYPTION_KEY"),
    ],
    ids=["hosts", "csrf_origins", "field_key"],
)
def test_the_production_settings_refuse_to_start(overrides, message):
    result = _import_prod(**overrides)
    assert result.returncode != 0
    assert "ImproperlyConfigured" in result.stderr
    assert message in result.stderr
