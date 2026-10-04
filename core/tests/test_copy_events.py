"""Round 159: 「复制」 a scrim or tournament into a new one (design 14.2, v6.51)."""

import re
from datetime import timedelta

import pytest
from django.core.management import call_command
from django.urls import reverse
from django.utils import timezone
from wagtail.test.utils.form_data import querydict_from_html

from accounts.tests.test_onboarding import _user
from core.services import weeks_ahead
from scrims.models import Scrim, ScrimFormat, ScrimStatus
from tournaments.models import Tournament, TournamentStatus
from tournaments.tests.test_adhoc_teams import _tournament


@pytest.fixture
def site(db):
    call_command("init_site", verbosity=0)


def _minute(moment):
    """As the browser's date-and-time box holds it (backoffice.widgets)."""
    return f"{timezone.localtime(moment):%Y-%m-%dT%H:%M}"


def _copy_form(client, url):
    """The copy page's form, and where it is sent (itself when the form names
    no address). The helper reads a ticked box without a value as "", which
    Django takes for unticked; a browser sends "on"."""
    html = client.get(url).content.decode()
    form = re.search(r'<form method="post" class="b-form"[^>]*>', html).group(0)
    named = re.search(r'action="([^"]+)"', form)
    action = named.group(1) if named else url
    data = querydict_from_html(html, form_index=0)
    for box in re.findall(r'<input[^>]*type="checkbox"[^>]*>', html):
        name = re.search(r'name="([^"]+)"', box)
        if name and " checked" in box and data.get(name.group(1)) == "":
            data[name.group(1)] = "on"
    return action, data


def test_how_far_a_copy_moves():
    now = timezone.now()
    assert weeks_ahead([], now) == 1
    assert weeks_ahead([None, now + timedelta(days=3)], now) == 1  # still ahead
    assert weeks_ahead([now - timedelta(days=3)], now) == 1
    assert weeks_ahead([now - timedelta(days=7)], now) == 2  # not today: ahead
    assert weeks_ahead([now - timedelta(days=365), now], now) == 53
    earliest = now - timedelta(days=365)
    assert earliest + timedelta(weeks=52) < now < earliest + timedelta(weeks=53)


@pytest.mark.django_db
def test_a_weekly_scrim_is_copied_to_next_week(site, client):
    start = (timezone.now() - timedelta(days=6)).replace(second=0, microsecond=0)
    old = Scrim.objects.create(
        title="周日下午 · 新人友好场159",
        description="新人也来。",
        format=ScrimFormat.OPEN_6V6,
        sjtu_only=True,
        status=ScrimStatus.PUBLISHED,
        starts_at=start,
        signup_closes_at=start - timedelta(hours=2),
    )
    manager = _user("s159@example.com", "内战管理员", "投稿者")
    client.force_login(manager)

    action, data = _copy_form(client, reverse("scrims:copy", args=[old.pk]))
    # Posting the copy makes a new scrim; the old one is never the instance.
    assert action == reverse("scrims:copy", args=[old.pk])
    assert data["title"] == old.title and data["description"].strip() == old.description
    assert data["format"] == ScrimFormat.OPEN_6V6 and data["sjtu_only"] == "on"
    week = timedelta(weeks=1)
    assert data["starts_at"] == _minute(start + week)
    assert data["signup_closes_at"] == _minute(start - timedelta(hours=2) + week)

    response = client.post(action, data)
    assert response.status_code == 302, response.content.decode()[:2000]
    new = Scrim.objects.exclude(pk=old.pk).get(title=old.title)
    assert new.status == ScrimStatus.DRAFT and new.sjtu_only
    assert new.starts_at == start + week
    assert new.created_by == manager
    # Even sent back to the copy address, the form makes a new scrim.
    client.post(reverse("scrims:copy", args=[old.pk]), data)
    third = Scrim.objects.exclude(pk__in=[old.pk, new.pk]).get(title=old.title)
    assert third.status == ScrimStatus.DRAFT and third.created_by == manager
    old.refresh_from_db()
    assert old.status == ScrimStatus.PUBLISHED and old.starts_at == start


@pytest.mark.django_db
def test_last_years_tournament_lands_this_year(site, client):
    opens = (timezone.now() - timedelta(days=380)).replace(second=0, microsecond=0)
    old = _tournament(
        title="新生杯159",
        summary="一年一度。",
        registration_opens_at=opens,
        registration_closes_at=opens + timedelta(days=14),
        starts_at=opens + timedelta(days=20),
        roster_min=5,
        roster_max=7,
        status=TournamentStatus.FINISHED,
        participant_contact="选手群 123456",
    )
    admin = _user("t159@example.com", "赛事管理员", "投稿者")
    client.force_login(admin)

    action, data = _copy_form(client, reverse("tournaments:copy", args=[old.pk]))
    assert action == reverse("tournaments:copy", args=[old.pk])
    shift = timedelta(weeks=55)  # 380 days is 54 weeks and 2 days
    assert data["registration_opens_at"] == _minute(opens + shift)
    assert data["starts_at"] == _minute(opens + timedelta(days=20) + shift)
    assert data["roster_max"] == "7"
    assert data["participant_contact"] == "选手群 123456"

    response = client.post(action, data)
    assert response.status_code == 302, response.content.decode()[:2000]
    new = Tournament.objects.exclude(pk=old.pk).get(title="新生杯159")
    assert new.status == TournamentStatus.DRAFT
    assert new.registration_opens_at == opens + shift
    assert new.registration_opens_at.weekday() == opens.weekday()
    client.post(reverse("tournaments:copy", args=[old.pk]), data)
    third = Tournament.objects.exclude(pk__in=[old.pk, new.pk]).get(title="新生杯159")
    assert third.status == TournamentStatus.DRAFT and third.created_by == admin
    old.refresh_from_db()
    assert old.status == TournamentStatus.FINISHED
    assert old.registration_opens_at == opens


@pytest.mark.django_db
def test_copy_is_in_the_menu_for_those_who_may_add(site, client):
    scrim = Scrim.objects.create(
        title="可复制159",
        format=ScrimFormat.RQ_5V5,
        status=ScrimStatus.PUBLISHED,
        starts_at=timezone.now() + timedelta(days=1),
    )
    tournament = _tournament(title="别人的赛事159")
    manager = _user("m159@example.com", "内战管理员", "投稿者")
    client.force_login(manager)
    listing = client.get(reverse("scrims:index")).content.decode()
    assert reverse("scrims:copy", args=[scrim.pk]) in listing
    response = client.get(reverse("tournaments:copy", args=[tournament.pk]))
    assert response.status_code != 200  # a scrim manager runs no tournaments
    assert not Tournament.objects.exclude(pk=tournament.pk).exists()

    from core.admin_manual import parts_for

    steps = "".join(step.text for part in parts_for(manager) for step in part.steps)
    assert "「更多 → 复制」" in steps


def test_every_form_field_is_copied_or_moved(db):
    """A field added to the form later must be decided: copied, moved, or left
    blank on purpose (then this list changes too)."""
    from backoffice.forms import ScrimForm, TournamentForm
    from scrims import services as scrims
    from tournaments import services as tournaments

    for form, services in ((ScrimForm, scrims), (TournamentForm, tournaments)):
        decided = set(services.COPIED_FIELDS) | set(services.COPIED_TIMES)
        assert set(form.base_fields) == decided, form.__name__
