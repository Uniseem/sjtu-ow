"""Round 120: who the visitor is, behind Caddy and a reverse proxy.

Caddy works out the visitor's address (honouring the proxies it trusts) and
sends it as X-Real-IP; Django's own REMOTE_ADDR is only the Caddy container,
so allauth's login limits used to count every visitor together.
"""

import re
from pathlib import Path

import pytest
from django.conf import settings as django_settings
from django.core.cache import cache
from django.test import RequestFactory
from django.urls import reverse
from django.utils import timezone

from accounts.adapter import AccountAdapter
from accounts.models import User
from core.ratelimit import client_ip

CADDYFILE = Path(django_settings.BASE_DIR, "deploy", "Caddyfile")


def test_the_visitor_is_whoever_caddy_names():
    request = RequestFactory().get(
        "/",
        HTTP_X_REAL_IP="203.0.113.7",
        HTTP_X_FORWARDED_FOR="198.51.100.1, 100.96.0.7",
        REMOTE_ADDR="172.18.0.5",
    )
    assert client_ip(request) == "203.0.113.7"


def test_x_forwarded_for_alone_names_nobody():
    """Its last entry is the outer reverse proxy once there is one."""
    request = RequestFactory().get(
        "/", HTTP_X_FORWARDED_FOR="203.0.113.7, 100.96.0.7", REMOTE_ADDR="10.0.0.9"
    )
    assert client_ip(request) == "10.0.0.9"


def test_allauth_asks_the_same_question():
    request = RequestFactory().get(
        "/", HTTP_X_REAL_IP="203.0.113.8", REMOTE_ADDR="172.18.0.5"
    )
    assert AccountAdapter().get_client_ip(request) == "203.0.113.8"


@pytest.mark.django_db
def test_failed_logins_count_per_visitor(client):
    cache.clear()
    User.objects.create_user(
        email="limited120@example.com",
        password="Correct-Horse-Battery-1",
        nickname="限流",
        agreed_terms_at=timezone.now(),
        agreed_cross_border_at=timezone.now(),
    )
    url = reverse("account_login")

    def attempt(ip, number):
        response = client.post(
            url,
            {"login": f"nobody{number}@example.com", "password": "wrong-password"},
            HTTP_X_REAL_IP=ip,
        )
        return response.content.decode()

    # The login page says what went wrong (it showed nothing before).
    assert "邮箱或密码不正确" in attempt("203.0.113.20", 0)
    for number in range(1, 10):
        assert "过多" not in attempt("203.0.113.20", number)
    assert "登录失败次数过多" in attempt("203.0.113.20", 99)
    # Someone else, behind the same Caddy, is not locked out.
    assert "过多" not in attempt("203.0.113.21", 100)


def test_every_route_to_django_names_the_visitor():
    text = CADDYFILE.read_text(encoding="utf-8")
    snippet = re.search(r"^\(django\) \{\n(.*?)^\}", text, re.S | re.M).group(1)
    assert "reverse_proxy web:8000" in snippet
    assert "header_up X-Real-IP {client_ip}" in snippet
    outside = text.replace(snippet, "")
    assert "reverse_proxy" not in outside
    assert outside.count("import django") >= 4


@pytest.mark.django_db
def test_a_whole_form_error_shows_once(client):
    from accounts.models import ContactMethod, ContactType

    user = User.objects.create_user(
        email="contact120@example.com",
        password="Correct-Horse-Battery-1",
        nickname="联系120",
        agreed_terms_at=timezone.now(),
        agreed_cross_border_at=timezone.now(),
    )
    ContactMethod.objects.create(user=user, type=ContactType.QQ, value="12345678")
    client.force_login(user)
    html = client.post(
        reverse("me_contacts"), {"type": ContactType.QQ, "value": "12345678"}
    ).content.decode()
    assert html.count('class="c-field__error" role="alert"') == 1
