"""Round 132: 「我的报名」 says when each match is (design 13.5, v6.27)."""

import re
from datetime import timedelta

import pytest
from django.urls import reverse
from django.utils import timezone

from tournaments import registration as reg
from tournaments.models import Tournament, TournamentStatus
from tournaments.tests.test_state_table import APPROVED, player


def _cells(html):
    return [
        cell.strip() for cell in re.findall(r"data-starts>(.*?)</td>", html, flags=re.S)
    ]


@pytest.mark.django_db
def test_team_entries_show_the_start(make, client):
    registration, captain, *_ = make(APPROVED)
    starts = timezone.now() + timedelta(days=3)
    Tournament.objects.filter(pk=registration.tournament.pk).update(starts_at=starts)
    client.force_login(captain)
    html = client.get(reverse("me_registrations")).content.decode()
    local = timezone.localtime(starts)
    assert _cells(html) == [f"{local:%Y.%m.%d} {local:%H:%M}"]

    Tournament.objects.filter(pk=registration.tournament.pk).update(starts_at=None)
    html = client.get(reverse("me_registrations")).content.decode()
    assert "未定" in _cells(html)[0]


@pytest.mark.django_db
def test_individual_entries_show_the_start(client):
    now = timezone.now()
    starts = now + timedelta(days=5)
    tournament = Tournament.objects.create(
        title="个人赛132",
        registration_mode="individual",
        registration_opens_at=now - timedelta(days=1),
        registration_closes_at=now + timedelta(days=2),
        starts_at=starts,
        status=TournamentStatus.PUBLISHED,
        published_at=now,
    )
    me = player("solo132@example.com", "散人132")
    reg.sign_up_individual(
        tournament=tournament,
        user=me,
        game_account_id=me.game_accounts.first().pk,
        roles=["damage"],
    )
    client.force_login(me)
    html = client.get(reverse("me_registrations")).content.decode()
    local = timezone.localtime(starts)
    assert _cells(html) == [f"{local:%Y.%m.%d} {local:%H:%M}"]


@pytest.mark.django_db
def test_the_registration_page_says_when(make, client):
    registration, captain, *_ = make(APPROVED)
    client.force_login(captain)
    url = registration.get_absolute_url()
    assert "data-detail-starts" not in client.get(url).content.decode()
    starts = timezone.now() + timedelta(days=4)
    Tournament.objects.filter(pk=registration.tournament.pk).update(starts_at=starts)
    local = timezone.localtime(starts)
    html = client.get(url).content.decode()
    assert f"比赛 {local:%Y.%m.%d} {local:%H:%M}" in html
