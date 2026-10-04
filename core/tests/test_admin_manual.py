"""Round 154: the admin manual shows each role its own part (design 14.1, v6.47)."""

import pytest
from django.contrib.auth.models import Group
from django.core.management import call_command
from django.urls import reverse

from accounts.tests.test_onboarding import _user
from core.admin_manual import parts_for


@pytest.fixture
def site(db):
    call_command("init_site", verbosity=0)


def _keys(user):
    return [part.key for part in parts_for(user)]


@pytest.mark.django_db
def test_each_role_gets_its_parts(site):
    assert _keys(_user("t154@example.com", "赛事管理员", "投稿者")) == ["tournaments"]
    assert _keys(_user("s154@example.com", "内战管理员", "投稿者")) == ["scrims"]
    assert _keys(_user("c154@example.com", "内容编辑", "投稿者")) == ["content"]
    assert _keys(_user("a154@example.com", "认证作者", "投稿者")) == ["authors"]
    assert _keys(_user("w154@example.com", "投稿者")) == []
    root = _user("r154@example.com")
    root.is_superuser = True
    root.save()
    assert _keys(root) == ["owner", "content", "tournaments", "scrims"]


@pytest.mark.django_db
def test_the_page_and_its_menu(site, client):
    manager = _user("tm154@example.com", "赛事管理员", "投稿者")
    client.force_login(manager)
    home = client.get(reverse("backoffice:home")).content.decode()
    assert reverse("admin_manual") in home
    page = client.get(reverse("admin_manual")).content.decode()
    assert 'data-manual-part="tournaments"' in page
    assert 'data-manual-part="content"' not in page
    # The step's own link, not the one in the side menu.
    review = reverse("registration_review_index")
    assert f'<a class="c-link" href="{review}">报名审核 →</a>' in page

    writer = _user("w154b@example.com", "投稿者")
    client.force_login(writer)
    assert (
        reverse("admin_manual")
        not in client.get(reverse("backoffice:home")).content.decode()
    )
    response = client.get(reverse("admin_manual"))
    assert response.status_code in (302, 403)


@pytest.mark.django_db
def test_every_link_in_the_manual_resolves(site, client):
    root = _user("r154b@example.com")
    root.is_superuser = True
    root.save()
    client.force_login(root)
    assert Group.objects.filter(name="内容编辑").exists()
    page = client.get(reverse("admin_manual")).content.decode()
    for key in ("owner", "content", "tournaments", "scrims"):
        assert f'data-manual-part="{key}"' in page
