"""Round 181: refusals that answer with a message instead of an error status,
which the guard sweeps of 042 and 179 could not see. Each test goes red when
its guard's condition is replaced by False."""

from unittest import mock

import pytest
from django.contrib.messages import get_messages
from django.urls import reverse
from wagtail.test.utils.form_data import querydict_from_html

from accounts.services import add_game_account, max_game_accounts
from core.models import FontFace, SiteSettings
from core.tests.test_admin_functions import _flagged, _staff, site  # noqa: F401
from moderation.models import ModerationItem


def _said(response):
    return [str(message) for message in get_messages(response.wsgi_request)]


@pytest.mark.django_db
def test_an_unknown_handling_is_refused_not_a_crash(site, client):  # noqa: F811
    client.force_login(_staff("editor181@example.com", "内容编辑"))
    item = _flagged()
    response = client.post(
        reverse("moderation_action", args=[item.pk]), {"action": "delete_everything"}
    )
    assert response.status_code == 302
    assert response["Location"] == reverse("moderation_detail", args=[item.pk])
    assert any("未知的处理方式" in message for message in _said(response))
    item.refresh_from_db()
    assert item.status == ModerationItem.Status.PENDING


@pytest.mark.django_db
def test_rebuilding_says_so_while_prerendering_is_off(site, client, settings):  # noqa: F811
    settings.PRERENDER_ENABLED = False
    client.force_login(_staff("root181@example.com", superuser=True))
    with (
        mock.patch("core.prerender.request_page") as one,
        mock.patch("core.prerender.request_all") as every,
    ):
        response = client.post(reverse("core_prerender_rebuild"), {"path": "/"})
    assert one.call_count == every.call_count == 0
    said = _said(response)
    assert any("预渲染当前是关闭的" in message for message in said), said
    assert not any("已排入队列" in message for message in said)


@pytest.mark.django_db
def test_a_weight_with_nothing_to_download(site, client, settings, tmp_path):  # noqa: F811
    from core.fonts import services as font_services
    from core.models import FontFamily

    settings.MEDIA_ROOT = tmp_path
    family = font_services.create_family(
        name="空字体181",
        source=FontFamily.Source.UPLOAD,
        license_type=FontFamily.License.OPEN_SOURCE,
    )
    face = FontFace.objects.create(family=family, weight=400)
    client.force_login(_staff("fonts181@example.com", superuser=True))
    response = client.get(reverse("core_font_face_download", args=[face.pk]))
    assert response.status_code == 302  # not an empty zip
    assert any("还没有可下载的文件" in message for message in _said(response))


@pytest.mark.django_db
def test_the_add_form_is_not_offered_at_the_limit(site, client):  # noqa: F811
    user = _staff("full181@example.com")
    for index in range(max_game_accounts()):
        add_game_account(user, battletag=f"Full{index}#1181")
    client.force_login(user)
    response = client.get(reverse("me_game_accounts") + "?new=1")
    assert response.status_code == 302
    assert any("最多绑定" in message for message in _said(response))


@pytest.mark.django_db
def test_editing_a_tournament_the_teams_outgrew_warns(site, client):  # noqa: F811
    """The form only checks roster_min when it changes; the site's team size
    can be lowered afterwards, and the next save says so."""
    from tournaments.tests.test_tournaments import _tournament

    tournament = _tournament(roster_min=5, roster_max=6, registration_mode="team")
    site_settings = SiteSettings.load()
    site_settings.team_max_members = 4
    site_settings.save()
    manager = _staff("manager181@example.com", "赛事管理员")
    manager.is_staff = True
    manager.save()
    client.force_login(manager)
    url = reverse("tournaments:edit", args=[tournament.pk])
    page = client.get(url).content.decode()
    data = querydict_from_html(page, form_index=0)
    data["title"] = "改了名字的赛事"
    response = client.post(url, data)
    assert response.status_code == 302, response.content.decode()[:2000]
    said = _said(response)
    assert any("大于全站战队人数上限 4" in message for message in said), said
