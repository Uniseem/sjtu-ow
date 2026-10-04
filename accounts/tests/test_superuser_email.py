"""Round 184: a superuser made on the server signs in without a code; a new
site has no mail server until that superuser sets one up (design 3.1, v6.63)."""

import pytest
from allauth.account.models import EmailAddress
from django.core.management import call_command
from django.core.management.base import CommandError
from django.urls import reverse
from django.utils import timezone

from accounts.models import User

PASSWORD = "Correct-Horse-Battery-1"


def _log_in(client, email):
    client.post(reverse("account_login"), {"login": email, "password": PASSWORD})
    return client.session.get("_auth_user_id")


@pytest.fixture
def superuser(db, monkeypatch):
    monkeypatch.setenv("DJANGO_SUPERUSER_PASSWORD", PASSWORD)
    call_command(
        "createsuperuser",
        interactive=False,
        email="Root184@Example.com",
        nickname="站长184",
        verbosity=0,
    )
    return User.objects.get(email="root184@example.com")


def test_the_command_records_the_email_as_verified(superuser):
    assert superuser.is_superuser
    assert list(
        EmailAddress.objects.filter(user=superuser).values_list(
            "email", "verified", "primary"
        )
    ) == [("root184@example.com", True, True)]


def test_that_superuser_signs_in_without_a_code(client, superuser):
    assert _log_in(client, "root184@example.com") == str(superuser.pk)


def test_everyone_else_still_needs_the_code(client, superuser):
    User.objects.create_user(
        email="member184@example.com",
        password=PASSWORD,
        nickname="普通成员184",
        agreed_terms_at=timezone.now(),
        agreed_cross_border_at=timezone.now(),
    )
    assert _log_in(client, "member184@example.com") is None


def test_superusers_already_there_are_left_alone(db, monkeypatch, superuser):
    EmailAddress.objects.filter(user=superuser).update(verified=False)
    monkeypatch.setenv("DJANGO_SUPERUSER_PASSWORD", PASSWORD)
    call_command(
        "createsuperuser",
        interactive=False,
        email="second184@example.com",
        nickname="第二个站长",
        verbosity=0,
    )
    assert not EmailAddress.objects.get(user=superuser).verified


def test_verify_email_lets_a_stuck_account_in(client, db):
    stuck = User.objects.create_user(
        email="stuck184@example.com",
        password=PASSWORD,
        nickname="收不到码",
        agreed_terms_at=timezone.now(),
        agreed_cross_border_at=timezone.now(),
    )
    EmailAddress.objects.create(
        user=stuck, email="old184@example.com", verified=True, primary=True
    )
    # What allauth leaves after a login attempt that wanted a code (183).
    EmailAddress.objects.create(
        user=stuck, email="stuck184@example.com", verified=False, primary=False
    )
    call_command("verify_email", "STUCK184@example.com", verbosity=0)
    assert EmailAddress.objects.get(email="stuck184@example.com").verified
    rows = dict(EmailAddress.objects.filter(user=stuck).values_list("email", "primary"))
    assert rows == {"stuck184@example.com": True, "old184@example.com": False}
    assert _log_in(client, "stuck184@example.com") == str(stuck.pk)


def test_verify_email_names_an_unknown_address(db):
    with pytest.raises(CommandError, match="没有用"):
        call_command("verify_email", "nobody184@example.com")
