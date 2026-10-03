"""Round 125: a member finding and tidying their own page (design 6.4, v6.21)."""

import pytest
from allauth.account.models import EmailAddress
from django.urls import reverse
from django.utils import timezone

from accounts.models import User

PASSWORD = "Correct-Horse-Battery-1"


def _member(email, **extra):
    user = User.objects.create_user(
        email=email,
        password=PASSWORD,
        nickname=email.split("@")[0][:12],
        agreed_terms_at=timezone.now(),
        agreed_cross_border_at=timezone.now(),
        **extra,
    )
    EmailAddress.objects.create(user=user, email=email, verified=True, primary=True)
    return user


@pytest.mark.django_db
def test_the_personal_centre_links_to_my_page(client):
    me = _member("me125@example.com")
    client.force_login(me)
    html = client.get(reverse("me_profile")).content.decode()
    assert f'href="{reverse("member_detail", args=[me.pk])}"' in html


@pytest.mark.django_db
def test_only_the_owner_sees_edit_and_hints(client):
    me = _member("owner125@example.com")
    url = reverse("member_detail", args=[me.pk])
    client.force_login(me)
    own = client.get(url).content.decode()
    assert "data-owner-edit" in own
    assert "还没写个人宣言" in own
    assert "还没选常用位置" in own
    assert "去找一支招募中的" in own  # the header links /teams/ for everyone
    client.force_login(_member("visitor125@example.com"))
    other = client.get(url).content.decode()
    assert "data-owner-edit" not in other
    assert "data-owner-hint" not in other


@pytest.mark.django_db
def test_filled_in_parts_need_no_hint(client):
    me = _member("done125@example.com", motto="冲就完了", main_role="tank")
    client.force_login(me)
    own = client.get(reverse("member_detail", args=[me.pk])).content.decode()
    assert "冲就完了" in own
    assert "还没写个人宣言" not in own
    assert "还没选常用位置" not in own
