"""The arena and roster pages on v3.0 (design 13.2.8, round 084): no Latin
eyebrows, fact lists in cards, the scrim's role counts as cards, related
articles as a card, and the member roster as numbered cards."""

from datetime import timedelta

import pytest
from allauth.account.models import EmailAddress
from django.utils import timezone

from content.models import ArticleCategory, ArticleIndexPage
from content.tests.test_content import _article, _tree, _user
from scrims.tests.test_scrims import make_scrim
from teams import services as team_services
from tournaments.models import Tournament, TournamentStatus
from tournaments.tests.test_state_table import player


def _main(response):
    html = response.content.decode("utf-8")
    return html[html.index("<main") : html.index("</main>")]


@pytest.fixture
def world(db):
    _tree()
    now = timezone.now()
    tournament = Tournament.objects.create(
        title="秋季杯",
        registration_opens_at=now - timedelta(days=1),
        registration_closes_at=now + timedelta(days=5),
        status=TournamentStatus.PUBLISHED,
        published_at=now,
    )
    scrim = make_scrim(title="周五内战")
    captain = player("cap@example.com", "队长")
    EmailAddress.objects.create(user=captain, email=captain.email, verified=True)
    team = team_services.create_team(user=captain, name="一支队")
    news = ArticleIndexPage.objects.get(slug="news")
    _article(
        news,
        ArticleCategory.objects.get(slug="match-report"),
        _user(),
        title="秋季杯战报",
        slug="report",
        tournament=tournament,
    )
    return tournament, scrim, team


@pytest.mark.parametrize(
    ("path", "word"),
    [
        ("/tournaments/", "TOURNAMENTS"),
        ("/scrims/", "SCRIMS"),
        ("/teams/", "TEAMS"),
        ("/members/", "MEMBERS"),
    ],
)
def test_lists_carry_no_latin_eyebrow(client, world, path, word):
    html = _main(client.get(path))
    assert word not in html
    assert "c-comments__count" not in html  # section counts use c-count


def test_detail_pages_set_their_facts_in_a_card(client, world):
    tournament, scrim, team = world
    for path in (
        tournament.get_absolute_url(),
        f"/scrims/{scrim.pk}/",
        team.get_absolute_url(),
    ):
        assert '<dl class="c-facts c-facts--card">' in _main(client.get(path)), path


def test_a_tournaments_articles_sit_in_a_card(client, world):
    tournament, _scrim, _team = world
    html = _main(client.get(tournament.get_absolute_url()))
    related = html[html.index('class="c-related"') :]
    assert "秋季杯战报" in related[: related.index("</section>")]
    assert "border-fg" not in html


def test_a_scrims_role_counts_are_three_cards(client, world):
    _tournament, scrim, _team = world
    html = _main(client.get(f"/scrims/{scrim.pk}/"))
    counts = html[html.index('<div class="c-rolestats">') :]
    counts = counts[: counts.index("</div>\n          <p")]
    assert counts.count('<div class="c-stat">') == 3
    assert "border-y" not in html


def test_the_member_count_reads_as_one_phrase(client, world):
    html = _main(client.get("/members/"))
    assert '<p class="c-pagehead__meta"><span>共 <span class="font-numeric">' in html


def test_the_roster_is_numbered_cards(client, world):
    html = _main(client.get("/members/"))
    roster = html[html.index('<ol class="c-roster"') : html.index("</ol>")]
    assert roster.count('<li class="c-roster__item" data-member>') == 1
    assert (
        '<span class="c-roster__no font-numeric" data-member-number>001</span>'
        in roster
    )
    assert '<span class="c-avatar" aria-hidden="true">队</span>' in roster
