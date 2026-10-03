"""Round 126: a player sees their own place in the split (design 9.2, v6.22).

Only their own: the public page still shows no split.
"""

from datetime import timedelta

import pytest
from django.urls import reverse
from django.utils import timezone

from scrims import notifications, services
from scrims.models import Role, Scrim, ScrimFormat, ScrimStatus
from scrims.tests.test_scrims import DIAMOND_3, make_user


def _scrim(fmt=ScrimFormat.RQ_5V5):
    return Scrim.objects.create(
        title="分队内战",
        format=fmt,
        status=ScrimStatus.PUBLISHED,
        starts_at=timezone.now() + timedelta(days=1),
    )


def _signup(scrim, email, nickname, roles=(Role.TANK,)):
    user = make_user(email, nickname, tank=DIAMOND_3)
    signup = services.sign_up(
        scrim=scrim,
        user=user,
        game_account_id=user.game_accounts.first().pk,
        roles=list(roles),
    )
    return user, signup


def _place(signup, team="", role="", selected=True):
    signup.is_selected = selected
    signup.team = team
    signup.assigned_role = role
    signup.save(update_fields=["is_selected", "team", "assigned_role"])


@pytest.mark.django_db
def test_the_wording_for_each_place():
    scrim = _scrim()
    _a_user, placed = _signup(scrim, "a126@example.com", "甲126")
    _b_user, bench = _signup(scrim, "b126@example.com", "乙126")
    _c_user, left_out = _signup(scrim, "c126@example.com", "丙126")
    assert services.placement(placed) == ""
    _place(placed, "a", Role.TANK)
    _place(bench, "", "", selected=True)
    _place(left_out, "", "", selected=False)
    assert services.placement(placed) == "A 队 · 坦克"
    assert services.placement(bench) == "替补"
    assert services.placement(left_out) == "这次没排上场"
    open_scrim = _scrim(ScrimFormat.OPEN_5V5)
    _d_user, open_signup = _signup(open_scrim, "d126@example.com", "丁126")
    _place(open_signup, "b", Role.SUPPORT)
    assert services.placement(open_signup) == "B 队"


@pytest.mark.django_db
def test_the_scrim_page_shows_only_my_place(client):
    scrim = _scrim()
    me, mine = _signup(scrim, "me126@example.com", "我126")
    _other, theirs = _signup(scrim, "other126@example.com", "他126")
    client.force_login(me)
    assert (
        "当前分队"
        not in client.get(reverse("scrim_detail", args=[scrim.pk])).content.decode()
    )
    _place(mine, "a", Role.TANK)
    _place(theirs, "b", Role.TANK)
    html = client.get(reverse("scrim_detail", args=[scrim.pk])).content.decode()
    assert "当前分队：<strong>A 队 · 坦克</strong>" in html
    assert "B 队" not in html
    client.logout()
    assert (
        "当前分队"
        not in client.get(reverse("scrim_detail", args=[scrim.pk])).content.decode()
    )


@pytest.mark.django_db
def test_my_scrims_lists_my_place(client):
    scrim = _scrim()
    me, mine = _signup(scrim, "list126@example.com", "列126")
    client.force_login(me)
    assert "还没分队" in client.get(reverse("me_scrims")).content.decode()
    _place(mine, "b", Role.TANK)
    assert "B 队 · 坦克" in client.get(reverse("me_scrims")).content.decode()


@pytest.mark.django_db
def test_the_reminder_tells_each_player_their_place(mailoutbox):
    scrim = _scrim()
    first, a_signup = _signup(scrim, "r1126@example.com", "提醒甲")
    second, b_signup = _signup(scrim, "r2126@example.com", "提醒乙")
    _place(a_signup, "a", Role.TANK)
    _place(b_signup, "b", Role.TANK)
    notifications.scrim_reminder(scrim)
    letters = {message.to[0]: message.body for message in mailoutbox}
    assert "A 队 · 坦克" in letters[first.email]
    assert "B 队" not in letters[first.email]
    assert "B 队 · 坦克" in letters[second.email]


# --- which group (round 138, design 9.2 v6.33) ------------------------------------


def _group(url):
    from core.models import SiteSettings

    site = SiteSettings.load()
    site.qq_group_url = url
    site.save()


GROUP_URL = "https://qm.qq.com/q/sjtu-ow-138"


@pytest.mark.django_db
def test_signed_up_players_are_told_which_group(client):
    _group(GROUP_URL)
    scrim = _scrim()
    me, _mine = _signup(scrim, "group138@example.com", "群138")
    client.force_login(me)
    page = client.get(reverse("scrim_detail", args=[scrim.pk])).content.decode()
    assert f'href="{GROUP_URL}"' in page
    client.force_login(make_user("nosign138@example.com", "没报138", tank=DIAMOND_3))
    page = client.get(reverse("scrim_detail", args=[scrim.pk])).content.decode()
    assert "data-group-link" not in page
    client.logout()
    page = client.get(reverse("scrim_detail", args=[scrim.pk])).content.decode()
    assert "data-group-link" not in page


@pytest.mark.django_db
def test_no_group_link_set_nothing_said(client):
    _group("")
    scrim = _scrim()
    me, _mine = _signup(scrim, "group138b@example.com", "群138b")
    client.force_login(me)
    page = client.get(reverse("scrim_detail", args=[scrim.pk])).content.decode()
    assert "data-group-link" not in page


@pytest.mark.django_db
def test_the_reminder_links_the_group(mailoutbox):
    _group(GROUP_URL)
    scrim = _scrim()
    _signup(scrim, "group138c@example.com", "群138c")
    notifications.scrim_reminder(scrim)
    assert GROUP_URL in mailoutbox[-1].body
    _group("")
    mailoutbox.clear()
    notifications.scrim_reminder(scrim)
    assert "社团 QQ 群" not in mailoutbox[-1].body
