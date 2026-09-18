"""deploy/healthcheck.py against production-like host and HTTPS settings.

The container healthcheck used to request http://127.0.0.1:8000/healthz with
no headers. In production that is a 400 (ALLOWED_HOSTS) and, once the host is
allowed, a redirect to https (SECURE_SSL_REDIRECT). Round 053 found it on the
first real deployment; nothing local could have.
"""

import importlib.util
import re
import urllib.error
from types import SimpleNamespace

import pytest
from django.conf import settings as django_settings

SITE = "sjtu.example.com"


def _load_script():
    path = django_settings.BASE_DIR / "deploy" / "healthcheck.py"
    spec = importlib.util.spec_from_file_location("deploy_healthcheck", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.fixture
def script(monkeypatch):
    monkeypatch.setenv("DJANGO_ALLOWED_HOSTS", f"{SITE},www.{SITE}")
    return _load_script()


@pytest.fixture
def production_like(settings, monkeypatch):
    from core import health

    settings.ALLOWED_HOSTS = [SITE]
    settings.SECURE_SSL_REDIRECT = True
    settings.SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")
    # The runner's own disk must not decide these results (round 045).
    usage = SimpleNamespace(total=100, used=50, free=50)
    monkeypatch.setattr(health.shutil, "disk_usage", lambda _path: usage)


def _as_client_headers(request):
    return {
        "HTTP_" + name.upper().replace("-", "_"): value
        for name, value in request.header_items()
    }


@pytest.mark.django_db
def test_a_bare_request_to_the_container_is_refused(client, production_like):
    """What the old healthcheck sent."""
    response = client.get("/healthz", HTTP_HOST="127.0.0.1:8000")
    assert response.status_code == 400


@pytest.mark.django_db
def test_the_scripts_request_reaches_healthz(
    client, production_like, script, worker_heartbeat
):
    request = script.build_request()
    response = client.get("/healthz", **_as_client_headers(request))
    assert response.status_code == 200, response.content.decode()


@pytest.mark.django_db
def test_without_the_proto_header_it_would_be_redirected(
    client, production_like, script
):
    response = client.get("/healthz", HTTP_HOST=script.site_host())
    assert response.status_code == 301


def test_the_script_uses_the_first_concrete_allowed_host(monkeypatch):
    monkeypatch.setenv("DJANGO_ALLOWED_HOSTS", " *, .example.org ,other.example")
    assert _load_script().site_host() == "example.org"


def test_the_script_fails_when_healthz_does_not_answer_200(script, monkeypatch):
    def unhealthy(request, timeout):
        raise urllib.error.HTTPError(request.full_url, 503, "Unavailable", {}, None)

    monkeypatch.setattr(script.urllib.request, "urlopen", unhealthy)
    assert script.main() == 1


def test_the_script_passes_on_200(script, monkeypatch):
    class Ok:
        status = 200

        def __enter__(self):
            return self

        def __exit__(self, *exc):
            return False

    monkeypatch.setattr(script.urllib.request, "urlopen", lambda *a, **k: Ok())
    assert script.main() == 0


def _compose():
    import yaml

    path = django_settings.BASE_DIR / "deploy" / "docker-compose.yml"
    return yaml.safe_load(path.read_text())


@pytest.mark.parametrize("service", ["web", "worker", "proxy"])
def test_every_service_comes_back_after_a_crash_or_reboot(service):
    """Round 053: none had a restart policy, so a reboot left the site down."""
    assert _compose()["services"][service]["restart"] == "unless-stopped"


def test_the_web_container_is_checked_with_the_script():
    test = _compose()["services"]["web"]["healthcheck"]["test"]
    assert test == ["CMD", "python", "/app/deploy/healthcheck.py"]


@pytest.mark.parametrize("service", ["web", "worker", "proxy"])
def test_every_service_rotates_its_logs(service):
    """Design 15.5, round 063: json-file never rotated, logs grew until full."""
    logging = _compose()["services"][service]["logging"]
    assert logging["driver"] == "json-file"
    assert logging["options"] == {"max-size": "10m", "max-file": "5"}


def test_no_log_records_the_visitor_ip():
    """Design 15.5 and the privacy policy: request logs carry no user IP.

    gunicorn logs the peer address, which is the Caddy container; Caddy
    itself writes no access log. Either change would start logging IPs.
    """
    deploy = django_settings.BASE_DIR / "deploy"
    caddyfile = (deploy / "Caddyfile").read_text()
    entrypoint = (deploy / "entrypoint-web.sh").read_text()
    assert not re.search(r"^\s*log\b", caddyfile, re.M)
    assert "--forwarded-allow-ips" not in entrypoint
    assert "--access-logformat" not in entrypoint


@pytest.mark.parametrize("service", ["web", "worker"])
def test_every_service_that_renders_pages_sees_the_static_files(service):
    """Round 064: without collectstatic's manifest every template that uses
    {% static %} fails in production, so the worker could not prerender."""
    volumes = _compose()["services"][service]["volumes"]
    assert any(v.split(":")[:2] == ["static", "/app/staticfiles"] for v in volumes)
