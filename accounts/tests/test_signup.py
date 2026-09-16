from datetime import timedelta

import pytest
from django.contrib.auth import get_user_model
from django.urls import reverse
from django.utils import timezone

from accounts.services import GROUP_EXTERNAL, GROUP_SJTU, ensure_user_groups
from core.middleware import OW_LOGGED_IN_COOKIE

User = get_user_model()

VALID_PASSWORD = "Correct-Horse-Battery-1"

VALID_SIGNUP = {
    "email": "player@example.com",
    "password1": VALID_PASSWORD,
    "password2": VALID_PASSWORD,
    "nickname": "测试昵称",
    "is_sjtu": "true",
    "agreed_terms": "on",
    "agreed_cross_border": "on",
}


def _signup(client, **overrides):
    data = {**VALID_SIGNUP, **overrides}
    return client.post(reverse("account_signup"), data)


@pytest.mark.django_db
def test_signup_requires_both_agreements(client):
    response = _signup(client, agreed_terms="", agreed_cross_border="on")
    assert response.status_code == 200
    assert User.objects.count() == 0
    response = _signup(client, agreed_terms="on", agreed_cross_border="")
    assert response.status_code == 200
    assert User.objects.count() == 0


@pytest.mark.django_db
def test_signup_nickname_length_bounds(client):
    response = _signup(client, nickname="一")
    assert response.status_code == 200
    assert User.objects.count() == 0
    response = _signup(client, nickname="十" * 17)
    assert response.status_code == 200
    assert User.objects.count() == 0
    response = _signup(client, nickname="两字")
    assert response.status_code == 302
    assert User.objects.filter(nickname="两字").exists()


@pytest.mark.django_db
def test_signup_rejects_weak_passwords(client):
    response = _signup(client, password1="12345678", password2="12345678")
    assert response.status_code == 200
    assert User.objects.count() == 0
    response = _signup(client, password1="short", password2="short")
    assert response.status_code == 200
    assert User.objects.count() == 0


@pytest.mark.django_db
def test_signup_email_is_case_insensitive_unique(client):
    assert _signup(client).status_code == 302
    response = _signup(client, email="Player@Example.com", nickname="另一个")
    assert User.objects.filter(email__iexact="player@example.com").count() == 1
    assert not User.objects.filter(nickname="另一个").exists()
    assert response.status_code in {200, 302}


@pytest.mark.django_db
def test_unverified_user_cannot_login(client):
    assert _signup(client).status_code == 302
    client.logout()
    response = client.post(
        reverse("account_login"),
        {"login": "player@example.com", "password": VALID_PASSWORD},
    )
    assert response.status_code in {200, 302}
    assert "_auth_user_id" not in client.session


@pytest.mark.django_db
def test_verified_user_can_login(client):
    assert _signup(client).status_code == 302
    code = client.session["account_email_verification_code"]["code"]
    response = client.post(
        reverse("account_email_verification_sent"),
        {"code": code},
    )
    assert response.status_code == 302
    client.logout()
    response = client.post(
        reverse("account_login"),
        {"login": "player@example.com", "password": VALID_PASSWORD},
    )
    assert response.status_code == 302
    assert "_auth_user_id" in client.session


@pytest.mark.django_db
def test_is_sjtu_assigns_and_switches_groups(client):
    ensure_user_groups()
    assert _signup(client, is_sjtu="true").status_code == 302
    user = User.objects.get(email="player@example.com")
    names = set(user.groups.values_list("name", flat=True))
    assert GROUP_SJTU in names
    assert GROUP_EXTERNAL not in names
    user.is_sjtu = False
    user.save()
    names = set(user.groups.values_list("name", flat=True))
    assert GROUP_EXTERNAL in names
    assert GROUP_SJTU not in names


@pytest.mark.django_db
def test_logged_in_hint_cookie_set_and_cleared(client):
    assert _signup(client).status_code == 302
    code = client.session["account_email_verification_code"]["code"]
    client.post(reverse("account_email_verification_sent"), {"code": code})
    client.logout()
    client.post(
        reverse("account_login"),
        {"login": "player@example.com", "password": VALID_PASSWORD},
    )
    client.get(reverse("home"))
    assert client.cookies.get(OW_LOGGED_IN_COOKIE)
    assert client.cookies[OW_LOGGED_IN_COOKIE].value == "1"
    client.post(reverse("account_logout"))
    client.get(reverse("home"))
    cookie = client.cookies.get(OW_LOGGED_IN_COOKIE)
    assert cookie is None or cookie.value == ""


@pytest.mark.django_db
def test_signup_stores_agreement_timestamps(client):
    before = timezone.now()
    assert _signup(client).status_code == 302
    user = User.objects.get(email="player@example.com")
    assert user.agreed_terms_at >= before
    assert user.agreed_cross_border_at >= before
    assert user.agreed_terms_at - user.agreed_cross_border_at <= timedelta(seconds=2)
