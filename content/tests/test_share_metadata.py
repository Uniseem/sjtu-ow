"""Design 13.14: each detail page's own share preview, and the sitemap (round 062).

Until round 062 tournament, team and scrim pages set only <title>; the
description, canonical URL and og:* tags were the site-wide defaults, so a
link pasted into a QQ group previewed as the homepage.
"""

import re
from datetime import datetime, timedelta

import pytest
from django.utils import timezone

from content.seo import DEFAULT_DESCRIPTION
from content.tests.test_content import _image
from scrims.models import ScrimFormat, ScrimStatus
from scrims.tests.test_scrims import make_scrim
from teams import services as team_services
from tournaments.models import Tournament, TournamentStatus
from tournaments.tests.test_state_table import player


def _meta(html, name):
    """The content of <meta property="og:…"> or <meta name="…">."""
    match = re.search(
        rf'<meta (?:property|name)="{re.escape(name)}" content="([^"]*)"', html
    )
    return match.group(1) if match else None


def _canonical(html):
    match = re.search(r'<link rel="canonical" href="([^"]*)"', html)
    return match.group(1) if match else None


def _tournament(**kwargs):
    now = timezone.now()
    options = {
        "title": "春季校内赛",
        "summary": "面向全校的 5v5 比赛",
        "registration_opens_at": now - timedelta(days=1),
        "registration_closes_at": now + timedelta(days=7),
        "roster_min": 5,
        "roster_max": 6,
        "status": TournamentStatus.PUBLISHED,
        "published_at": now,
    }
    options.update(kwargs)
    return Tournament.objects.create(**options)


@pytest.mark.django_db
def test_a_tournament_previews_with_its_name_summary_and_cover(client):
    tournament = _tournament(cover=_image("tournament-cover"))
    html = client.get(tournament.get_absolute_url()).content.decode("utf-8")

    assert _meta(html, "og:title") == "春季校内赛"
    assert _meta(html, "og:description") == "面向全校的 5v5 比赛"
    assert _meta(html, "description") == "面向全校的 5v5 比赛"
    assert _meta(html, "og:image").startswith("http://testserver/media/")
    assert _canonical(html) == f"http://testserver{tournament.get_absolute_url()}"
    assert _meta(html, "og:url") == _canonical(html)


@pytest.mark.django_db
def test_without_a_summary_the_site_description_is_used(client):
    tournament = _tournament(summary="")
    html = client.get(tournament.get_absolute_url()).content.decode("utf-8")
    assert _meta(html, "og:description") == DEFAULT_DESCRIPTION


@pytest.mark.django_db
def test_a_team_previews_with_its_name_description_and_logo(client):
    captain = player("share-captain@example.com", "分享队长")
    team = team_services.create_team(
        user=captain, name="分享测试队", description="周末固定开黑", logo=_image("logo")
    )
    html = client.get(team.get_absolute_url()).content.decode("utf-8")

    assert _meta(html, "og:title") == "分享测试队"
    assert _meta(html, "og:description") == "周末固定开黑"
    assert _meta(html, "og:image").startswith("http://testserver/media/")
    assert _canonical(html) == f"http://testserver{team.get_absolute_url()}"


@pytest.mark.django_db
def test_a_scrim_previews_with_its_time_format_and_signups(client):
    starts = timezone.make_aware(datetime(2030, 5, 3, 19, 30))
    scrim = make_scrim(title="周五内战", starts_at=starts, format=ScrimFormat.RQ_5V5)
    html = client.get(f"/scrims/{scrim.pk}/").content.decode("utf-8")

    assert _meta(html, "og:title") == "周五内战 · 5月3日 19:30"
    assert _meta(html, "og:description") == (
        f"{scrim.get_format_display()} · 已报名 0 人"
    )
    assert _canonical(html) == f"http://testserver/scrims/{scrim.pk}/"


@pytest.mark.django_db
def test_the_sitemap_lists_public_scrims_only(client):
    shown = make_scrim(title="公开的内战")
    draft = make_scrim(title="草稿内战", status=ScrimStatus.DRAFT)
    cancelled = make_scrim(title="取消的内战", status=ScrimStatus.CANCELLED)

    xml = client.get("/sitemap.xml").content.decode("utf-8")

    assert f"/scrims/{shown.pk}/</loc>" in xml
    assert f"/scrims/{draft.pk}/</loc>" not in xml
    assert f"/scrims/{cancelled.pk}/</loc>" not in xml
