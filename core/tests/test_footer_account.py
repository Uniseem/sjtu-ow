"""Round 160: the footer 「账号」 column follows the visitor (design 13.2.7)."""

import re

import pytest
from django.core.management import call_command
from django.urls import reverse

from accounts.tests.test_onboarding import _user


@pytest.fixture
def site(db):
    call_command("init_site", verbosity=0)


def _column(html):
    match = re.search(r'<nav id="slot-footer-account".*?</nav>', html, re.S)
    assert match, "no footer account column"
    return match.group(0)


@pytest.mark.django_db
def test_visitors_are_offered_sign_in(site, client):
    column = _column(client.get(reverse("members")).content.decode())
    assert reverse("account_login") in column
    assert reverse("account_signup") in column
    assert reverse("me_registrations") not in column


@pytest.mark.django_db
def test_members_get_their_own_pages(site, client):
    client.force_login(_user("f160@example.com"))
    column = _column(client.get(reverse("members")).content.decode())
    for name in ("me_profile", "me_registrations", "me_teams"):
        assert reverse(name) in column
    assert reverse("account_login") not in column
    assert reverse("account_signup") not in column

    # A prerendered page asks for it with the rest of its slots.
    fragment = client.get(
        reverse("state_fragment"), {"slots": "account,footer-account"}
    ).content.decode()
    column = _column(fragment)
    assert 'hx-swap-oob="true"' in column
    assert reverse("me_teams") in column and reverse("account_login") not in column
