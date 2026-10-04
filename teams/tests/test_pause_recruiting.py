"""Round 180: stopping a captain stops their teams advertising themselves as
recruiting (design 3.7, v6.62)."""

from unittest import mock

import pytest
from django.contrib.messages import get_messages
from django.urls import reverse

from accounts.models import User
from accounts.services import after_deactivation
from core.tests.test_admin_safety import _player, _superuser, site  # noqa: F401
from teams import services
from teams.models import Team


def _stop(user):
    User.objects.filter(pk=user.pk).update(is_active=False)
    user.refresh_from_db()
    return after_deactivation(user)


@pytest.mark.django_db
def test_only_the_teams_they_captain_and_recruit_for_are_paused(site):  # noqa: F811
    captain = _player("cap180@example.com", "要停用的队长")
    led = services.create_team(user=captain, name="他带的队")
    quiet = services.create_team(user=captain, name="本来就不招")
    Team.objects.filter(pk=quiet.pk).update(is_recruiting=False)
    other = services.create_team(
        user=_player("other180@example.com", "别的队长"), name="他只是队员"
    )
    application = services.apply_to_team(team=other, user=captain, roles={"tank": True})
    services.approve_application(application=application, actor=other.captain())

    with mock.patch("core.prerender.request_page") as request_page:
        paused = _stop(captain)

    assert paused == [led]
    assert not Team.objects.get(pk=led.pk).is_recruiting
    assert Team.objects.get(pk=other.pk).is_recruiting
    urls = [call.args[0] for call in request_page.call_args_list]
    assert led.get_absolute_url() in urls and "/teams/" in urls
    assert other.get_absolute_url() not in urls


@pytest.mark.django_db
def test_the_recruiting_filters_no_longer_list_it(site):  # noqa: F811
    captain = _player("filter180@example.com", "筛选里的队长")
    team = services.create_team(user=captain, name="招人的队")
    assert team in services.open_teams(recruiting_only=True)
    assert team in services.open_teams(role="tank")

    _stop(captain)

    assert team not in services.open_teams(recruiting_only=True)
    assert team not in services.open_teams(role="tank")
    assert team in services.open_teams()  # still listed, as 暂不招募


@pytest.mark.django_db
def test_nothing_to_redo_when_nothing_recruits(site):  # noqa: F811
    member = _player("plain180@example.com", "普通成员180")
    with mock.patch("core.prerender.request_page") as request_page:
        assert _stop(member) == []
    assert request_page.call_count == 0


@pytest.mark.django_db
def test_the_admin_is_told_the_teams_were_paused(client, site):  # noqa: F811
    admin = _superuser()
    captain = _player("told180@example.com", "后台停用的队长")
    team = services.create_team(user=captain, name="被暂停的队")
    client.force_login(admin)
    response = client.post(
        reverse("wagtailusers_users:edit", args=[captain.pk]),
        {
            "email": captain.email,
            "nickname": captain.nickname,
            "is_sjtu": "on",
            "deactivation_note": "测试停用",
        },
    )
    said = [str(message) for message in get_messages(response.wsgi_request)]
    assert any("「被暂停的队」已改成暂不招募" in message for message in said), said
    assert not Team.objects.get(pk=team.pk).is_recruiting
