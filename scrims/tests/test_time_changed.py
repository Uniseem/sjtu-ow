"""Round 139: moving a scrim tells everyone signed up (design 9.1, v6.34)."""

from datetime import timedelta

import pytest
from django.core import mail
from django.urls import reverse
from django.utils import timezone
from wagtail.test.utils.form_data import querydict_from_html

from scrims import services
from scrims.models import Scrim, ScrimStatus
from scrims.tests.test_my_placement import _scrim, _signup


def _moved():
    return [m for m in mail.outbox if "内战时间改了" in m.subject]


def _at(scrim, delta, **extra):
    Scrim.objects.filter(pk=scrim.pk).update(starts_at=timezone.now() + delta, **extra)
    scrim.refresh_from_db()
    return scrim.starts_at


@pytest.mark.django_db
def test_everyone_signed_up_hears(django_capture_on_commit_callbacks):
    scrim = _scrim()
    first, _ = _signup(scrim, "m139a@example.com", "改期甲")
    second, _ = _signup(scrim, "m139b@example.com", "改期乙")
    old = _at(scrim, timedelta(days=1), reminder_sent_at=timezone.now())
    new = _at(scrim, timedelta(days=2))
    mail.outbox.clear()
    with django_capture_on_commit_callbacks(execute=True):
        assert services.time_changed(scrim, old)
    letters = _moved()
    assert sorted(m.to[0] for m in letters) == sorted([first.email, second.email])
    body = letters[0].body
    assert f"{timezone.localtime(old):%Y-%m-%d %H:%M}" in body
    assert f"{timezone.localtime(new):%Y-%m-%d %H:%M}" in body
    scrim.refresh_from_db()
    assert scrim.reminder_sent_at is None


@pytest.mark.django_db
def test_nothing_said_when_nothing_moved(django_capture_on_commit_callbacks):
    scrim = _scrim()
    _signup(scrim, "m139c@example.com", "改期丙")
    old = _at(scrim, timedelta(days=1))
    mail.outbox.clear()
    with django_capture_on_commit_callbacks(execute=True):
        assert not services.time_changed(scrim, old)
        assert not services.time_changed(scrim, None)
        _at(scrim, -timedelta(hours=1))
        assert not services.time_changed(scrim, old)
        _at(scrim, timedelta(days=3), status=ScrimStatus.DRAFT)
        assert not services.time_changed(scrim, old)
    assert _moved() == []


@pytest.mark.django_db
def test_saving_in_the_admin_sends_it(client, django_capture_on_commit_callbacks):
    from accounts.models import User

    scrim = _scrim()
    _signup(scrim, "m139d@example.com", "改期丁")
    admin = User.objects.create_superuser(
        email="root139s@example.com",
        password="Correct-Horse-Battery-1",
        nickname="站长139s",
        agreed_terms_at=timezone.now(),
        agreed_cross_border_at=timezone.now(),
    )
    client.force_login(admin)
    url = reverse("scrims:edit", args=[scrim.pk])
    data = querydict_from_html(
        client.get(url).content.decode(), form_id="w-editor-form"
    )
    later = timezone.localtime(timezone.now() + timedelta(days=4))
    data["starts_at"] = f"{later:%Y-%m-%d %H:%M}"
    mail.outbox.clear()
    with django_capture_on_commit_callbacks(execute=True):
        response = client.post(url, data)
    assert response.status_code == 302, response.content.decode()[:2000]
    assert [m.to for m in _moved()] == [["m139d@example.com"]]
