"""Round 139, reworked in 201: moving a published scrim mails nobody on saving;
「通知报名的人」 tells everyone signed up, from when to when (design 9.1,
10.4, v7.5; v6.34 mailed on every save that moved the time)."""

from datetime import timedelta

import pytest
from django.core import mail
from django.urls import reverse
from django.utils import timezone
from wagtail.test.utils.form_data import querydict_from_html

from core import services as core_services
from scrims import services
from scrims.models import Scrim, ScrimStatus
from scrims.tests.test_my_placement import _scrim, _signup
from tournaments.tests.test_time_changed import _admin, smtp, worker  # noqa: F401


def _updates():
    return [m for m in mail.outbox if "内战有更新" in m.subject]


def _at(scrim, delta, **extra):
    Scrim.objects.filter(pk=scrim.pk).update(starts_at=timezone.now() + delta, **extra)
    scrim.refresh_from_db()
    return scrim.starts_at


@pytest.mark.django_db
def test_moving_mails_nobody_and_keeps_what_they_knew(
    django_capture_on_commit_callbacks,
):
    scrim = _scrim()
    _signup(scrim, "m201a@example.com", "改期甲")
    old = _at(scrim, timedelta(days=1), reminder_sent_at=timezone.now())
    _at(scrim, timedelta(days=2))
    mail.outbox.clear()
    with django_capture_on_commit_callbacks(execute=True):
        assert services.note_time_change(scrim, old)
    assert mail.outbox == []
    scrim.refresh_from_db()
    assert scrim.moved_from == old
    assert scrim.reminder_sent_at is None


@pytest.mark.django_db
def test_nothing_noted_when_nothing_moved():
    scrim = _scrim()
    _signup(scrim, "m201c@example.com", "改期丙")
    old = _at(scrim, timedelta(days=1))
    assert not services.note_time_change(scrim, old)
    assert not services.note_time_change(scrim, None)
    _at(scrim, -timedelta(hours=1))
    assert not services.note_time_change(scrim, old)
    _at(scrim, timedelta(days=3), status=ScrimStatus.DRAFT)
    assert not services.note_time_change(scrim, old)
    scrim.refresh_from_db()
    assert scrim.moved_from is None


@pytest.mark.django_db
def test_saving_in_the_admin_mails_nobody_then_everyone_signed_up_hears(
    client,
    smtp,  # noqa: F811
    worker,  # noqa: F811
    django_capture_on_commit_callbacks,
):
    scrim = _scrim()
    first, _ = _signup(scrim, "m201d@example.com", "改期丁")
    second, _ = _signup(scrim, "m201e@example.com", "改期戊")
    old = scrim.starts_at
    client.force_login(_admin("root201s@example.com"))
    url = reverse("scrims:edit", args=[scrim.pk])
    data = querydict_from_html(client.get(url).content.decode(), form_index=0)
    later = timezone.localtime(timezone.now() + timedelta(days=4))
    data["starts_at"] = f"{later:%Y-%m-%d %H:%M}"
    mail.outbox.clear()
    with django_capture_on_commit_callbacks(execute=True):
        response = client.post(url, data)
    assert response.status_code == 302, response.content.decode()[:2000]
    assert mail.outbox == []
    assert "报名的人还不知道" in client.get(url).content.decode()

    notify = reverse("announce", args=["scrim", scrim.pk]) + "?to=participants"
    preview = client.get(notify).content.decode()
    assert "内战有更新" in preview and "2 人" in preview
    with django_capture_on_commit_callbacks(execute=True):
        client.post(notify, {"to": "participants", "note": ""})
    letters = _updates()
    assert sorted(m.to[0] for m in letters) == sorted([first.email, second.email])
    assert f"{timezone.localtime(old):%Y-%m-%d %H:%M}" in letters[0].body
    assert "报名的人还不知道" not in client.get(url).content.decode()


@pytest.mark.django_db
def test_a_draft_cannot_notify_the_people_signed_up(smtp):  # noqa: F811
    scrim = _scrim()
    _signup(scrim, "m201f@example.com", "改期己")
    Scrim.objects.filter(pk=scrim.pk).update(status=ScrimStatus.DRAFT)
    scrim.refresh_from_db()
    with pytest.raises(core_services.AnnouncementError, match="发布之后"):
        core_services.announce(
            kind="scrim",
            obj=scrim,
            actor=_admin("root201d@example.com"),
            audience="participants",
        )
