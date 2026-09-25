"""Round 068: 「我的内战」 is part of the personal centre.

/me/scrims/ existed since round 020 but the nav never linked it, and
/me/registrations/ kept a 「后续里程碑」 placeholder from M4.
"""

import pytest
from django.urls import reverse
from django.utils import timezone

from accounts.models import User


@pytest.fixture
def member(db):
    now = timezone.now()
    return User.objects.create_user(
        email="nav@example.com",
        password="Correct-Horse-Battery-1",
        nickname="导航",
        agreed_terms_at=now,
        agreed_cross_border_at=now,
    )


@pytest.mark.django_db
def test_the_registrations_page_points_at_my_scrims(client, member):
    client.force_login(member)

    html = client.get(reverse("me_registrations")).content.decode()

    assert reverse("me_scrims") in html
    assert "后续里程碑" not in html
    assert "即将开放" not in html


@pytest.mark.django_db
def test_my_scrims_sits_inside_the_personal_centre(client, member):
    client.force_login(member)

    html = client.get(reverse("me_scrims")).content.decode()

    # The shared nav is rendered, with this page marked as current.
    assert reverse("me_registrations") in html
    assert reverse("me_security") in html
    assert "我的内战" in html


@pytest.mark.django_db
def test_the_nav_lists_my_scrims_on_every_personal_page(client, member):
    client.force_login(member)

    html = client.get(reverse("me_profile")).content.decode()

    assert reverse("me_scrims") in html
