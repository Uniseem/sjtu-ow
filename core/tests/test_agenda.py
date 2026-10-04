"""Round 156: 「我的安排」 on the homepage (design 5.2, v6.48)."""

import re
from datetime import timedelta

import pytest
from django.core.management import call_command
from django.urls import reverse
from django.utils import timezone

from core.agenda import items_for
from scrims.models import ScrimStatus
from scrims.tests.test_my_placement import _place, _scrim, _signup
from tournaments.models import Tournament, TournamentStatus
from tournaments.tests.test_state_table import APPROVED, make  # noqa: F401


@pytest.fixture
def site(db):
    call_command("init_site", verbosity=0)


def _titles(html):
    """Only the agenda's own rows; the public 「近期」 cards repeat the titles."""
    return re.findall(
        r'data-agenda-item>.*?class="c-stretch">([^<]+)</a>', html, flags=re.S
    )


@pytest.mark.django_db
def test_my_signups_in_time_order(site, client, make):  # noqa: F811
    registration, captain, *_ = make(APPROVED)
    Tournament.objects.filter(pk=registration.tournament.pk).update(
        starts_at=timezone.now() + timedelta(days=3)
    )
    scrim = _scrim()  # tomorrow
    me, mine = _signup(scrim, "agenda156@example.com", "安排156")
    _place(mine, "a", "tank")
    from tournaments.tests.test_adhoc_teams import _tournament

    cup = _tournament(title="没定时间杯156")
    from tournaments import registration as reg

    reg.sign_up_individual(
        tournament=cup,
        user=me,
        game_account_id=me.game_accounts.first().pk,
        roles=["tank"],
    )
    # The captain of the approved team is on its roster too.
    client.force_login(captain)
    html = client.get("/").content.decode()
    assert registration.tournament.title in _titles(html)
    assert "已通过" in html[html.index("data-my-agenda") :]

    client.force_login(me)
    html = client.get("/").content.decode()
    assert _titles(html) == [scrim.title, "没定时间杯156"]
    block = html[html.index("data-my-agenda") :]
    assert "A 队 · 坦克" in block and "等待编队" in block and "时间未定" in block
    slot = client.get(reverse("state_fragment"), {"slots": "my-agenda"}).content
    assert scrim.title in slot.decode()


@pytest.mark.django_db
def test_past_cancelled_and_strangers_see_nothing(site, client):
    scrim = _scrim()
    me, _mine = _signup(scrim, "past156@example.com", "过去156")
    from scrims.models import Scrim

    Scrim.objects.filter(pk=scrim.pk).update(
        starts_at=timezone.now() - timedelta(days=1)
    )
    assert items_for(me) == []
    Scrim.objects.filter(pk=scrim.pk).update(
        starts_at=timezone.now() + timedelta(days=1), status=ScrimStatus.CANCELLED
    )
    assert items_for(me) == []
    client.force_login(me)
    assert "data-agenda-empty" in client.get("/").content.decode()
    client.logout()
    assert "data-my-agenda" not in client.get("/").content.decode()


@pytest.mark.django_db
def test_a_cancelled_tournament_leaves_the_list(site, make):  # noqa: F811
    registration, captain, *_ = make(APPROVED)
    assert [item.title for item in items_for(captain)] == [
        registration.tournament.title
    ]
    Tournament.objects.filter(pk=registration.tournament.pk).update(
        status=TournamentStatus.CANCELLED
    )
    assert items_for(captain) == []
