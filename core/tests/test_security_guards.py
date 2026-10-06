"""Security checks that had no test until round 059's guard sweep."""

import json
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


@pytest.mark.parametrize(
    "url",
    [
        "https://127.0.0.1/font.ttf",
        "https://10.0.0.8/font.ttf",
        "https://192.168.1.1/font.ttf",
        "https://169.254.169.254/latest/meta-data/",  # cloud metadata
        "https://[::1]/font.ttf",
    ],
)
def test_addresses_inside_our_network_are_refused(url):
    """Round 179: the tests for this went with the webhooks in 067."""
    with pytest.raises(UnsafeUrl, match="内网"):
        assert_public_https_url(url)


def test_a_name_that_resolves_inside_is_refused_too(monkeypatch):
    import ipaddress

    from core import net

    monkeypatch.setattr(
        net,
        "resolved_addresses",
        lambda host, port: [
            ipaddress.ip_address("93.184.216.34"),
            ipaddress.ip_address("10.1.2.3"),
        ],
    )
    with pytest.raises(UnsafeUrl, match="内网"):
        assert_public_https_url("https://fonts.example.com/x.woff2")
    monkeypatch.undo()
    assert_public_https_url("https://93.184.216.34/font.ttf")  # no DNS needed


def test_a_redirect_into_our_network_is_refused():
    """Round 179: a public address can answer 302 to an internal one."""
    import urllib.request
    from email.message import Message

    from core.fonts.download import DownloadError, _SafeRedirectHandler

    handler = _SafeRedirectHandler()
    request = urllib.request.Request("https://93.184.216.34/font.ttf")
    with pytest.raises(DownloadError, match="内网"):
        handler.redirect_request(
            request, None, 302, "Found", Message(), "https://169.254.169.254/"
        )
    onward = handler.redirect_request(
        request, None, 302, "Found", Message(), "https://93.184.216.35/font.ttf"
    )
    assert onward.full_url == "https://93.184.216.35/font.ttf"


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
    return _run_in_prod_env("import sjtu_ow.settings.prod", **overrides)


def _run_in_prod_env(code, **overrides):
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
        [sys.executable, "-c", code],
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


def test_the_production_middleware_keeps_everything_base_has():
    """Round 068: prod.py replaces MIDDLEWARE wholesale and had silently
    dropped the prerender-miss fallback, so production never regenerated a
    missing static page on demand."""
    code = (
        "import json, sjtu_ow.settings.base as b, sjtu_ow.settings.prod as p; "
        "print(json.dumps([m for m in b.MIDDLEWARE if m not in p.MIDDLEWARE]))"
    )
    result = _run_in_prod_env(code)
    assert result.returncode == 0, result.stderr
    assert json.loads(result.stdout.strip().splitlines()[-1]) == []


def test_prod_logging_sends_request_errors_to_stdout():
    """210 复核 C3: production's 500 tracebacks must reach the container's
    stdout; Django's own default django.request handlers are off in prod."""
    code = (
        "import sjtu_ow.settings.prod as p\n"
        "request = p.LOGGING['loggers']['django.request']\n"
        "assert request['handlers'] == ['console'] and request['level'] == 'ERROR'\n"
        "assert not request['propagate']\n"
        "errors = p.LOGGING['loggers']['sjtu_ow.errors']\n"
        "assert errors['handlers'] == ['console']\n"
    )
    assert _run_in_prod_env(code).returncode == 0
