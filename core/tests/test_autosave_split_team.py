"""Round 207 (design 9.5, 7.1, 13.17; v7.11): the last two pages that had a
save button. The scrim split page saves every tick and every move; the
captain's 「战队资料」 saves itself, a chosen logo goes up at once and once.
"""

import io
import json
import re

import pytest
from django.core.files.uploadedfile import SimpleUploadedFile
from django.core.management import call_command
from django.urls import reverse
from PIL import Image as PILImage
from wagtail.images import get_image_model
from wagtail.models import ModelLogEntry

from accounts.tests.test_onboarding import _user
from scrims import services as scrim_services
from scrims.tests.test_my_placement import _scrim, _signup
from scrims.tests.test_scrims import DIAMOND_3
from teams import services as team_services

AUTOSAVE = {"HTTP_X_AUTOSAVE": "1", "HTTP_ACCEPT": "application/json"}


@pytest.fixture
def site(db):
    call_command("init_site", verbosity=0)


def _save(client, url, data):
    return json.loads(client.post(url, data, **AUTOSAVE).content)


# --- the split page ------------------------------------------------------------------


@pytest.fixture
def board(site, client):
    """A 5v5 scrim with ten placed players, and its manager signed in."""
    scrim = _scrim()
    signups = [
        _signup(scrim, f"p{n}-207@example.com", f"选手{n}")[1] for n in range(10)
    ]
    scrim_services.set_selection(scrim=scrim, signup_ids=[s.pk for s in signups])
    scrim_services.save_teams(
        scrim=scrim,
        placements={
            s.pk: ("a" if n < 5 else "b", "tank", DIAMOND_3)
            for n, s in enumerate(signups)
        },
    )
    client.force_login(_user("split207@example.com", "内战管理员"))
    return scrim, signups, reverse("scrim_split", args=[scrim.pk])


def _teams(signups, **moves):
    data = {"part": "teams"}
    for n, signup in enumerate(signups):
        data[f"team-{signup.pk}"] = "a" if n < 5 else "b"
        data[f"role-{signup.pk}"] = "tank"
    for pk, team in moves.items():
        data[f"team-{pk}"] = team
    return data


@pytest.mark.django_db
def test_unticking_saves_and_takes_the_player_off_the_board(board, client):
    scrim, signups, url = board
    gone = signups[0]
    keep = [s.pk for s in signups[1:]]
    answer = _save(client, url, {"part": "pick", "signups": keep})
    assert answer["ok"] and answer["saved"] == ["signups"]
    gone.refresh_from_db()
    assert not gone.is_selected and gone.team == ""
    html = answer["replace"]["[data-split-board]"]
    assert f'data-signup="{gone.pk}"' not in html
    assert f'data-signup="{signups[1].pk}"' in html
    assert "data-autosave" in html  # the board that came in saves itself too


@pytest.mark.django_db
def test_a_move_saves_and_the_copy_text_follows(board, client):
    scrim, signups, url = board
    moved = signups[0]
    answer = _save(client, url, _teams(signups, **{str(moved.pk): ""}))
    assert answer["saved"] == ["teams"]
    moved.refresh_from_db()
    assert moved.team == "" and moved.is_selected  # in the buffer, still on tonight
    copy = answer["replace"]["[data-split-copy]"]
    assert moved.user.nickname not in copy and signups[1].user.nickname in copy
    assert set(answer["replace"]) >= {
        '[data-team-problem="a"]',
        '[data-team-problem="b"]',
    }


@pytest.mark.django_db
def test_each_kind_of_edit_is_one_log_entry(board, client):
    scrim, signups, url = board
    every = [s.pk for s in signups]
    for _ in range(3):
        _save(client, url, {"part": "pick", "signups": every})
        _save(client, url, _teams(signups))
    entries = ModelLogEntry.objects.filter(object_id=str(scrim.pk))
    assert entries.filter(action="scrims.select").count() == 1
    assert entries.filter(action="scrims.save_teams").count() == 1


def test_a_move_on_the_board_tells_the_form():
    """Scripts that move cards change hidden values, which fire no event of
    their own: without this the board would never save itself."""
    from pathlib import Path

    from django.conf import settings

    source = (Path(settings.BASE_DIR) / "static/js/scrim-split.js").read_text(
        encoding="utf-8"
    )
    body = source.split("function moved()", 1)[1].split("// Design 9.5", 1)[0]
    assert '"[data-teams-moved]"' in body and 'new Event("change"' in body
    assert source.count("moved();") == 2  # after a drag that moved, after a button


# --- the captain's 战队资料 ---------------------------------------------------------


@pytest.fixture
def team(site, client):
    captain = _user("cap207@example.com")
    team = team_services.create_team(user=captain, name="自动保存队")
    client.force_login(captain)
    return team


def _png():
    buffer = io.BytesIO()
    PILImage.new("RGB", (32, 32), (155, 58, 51)).save(buffer, format="PNG")
    return SimpleUploadedFile("logo.png", buffer.getvalue(), content_type="image/png")


def _profile(team, **changes):
    data = {
        "form": "profile",
        "name": team.name,
        "description": team.description,
        "is_recruiting": "on",
        "member_contact": team.member_contact,
    }
    data.update(changes)
    return data


@pytest.mark.django_db
def test_a_taken_name_is_kept_and_the_rest_saved(team, client, settings, tmp_path):
    settings.MEDIA_ROOT = tmp_path
    team_services.create_team(user=_user("other207@example.com"), name="别人的队")
    url = reverse("team_manage", args=[team.pk])
    answer = _save(client, url, _profile(team, name="别人的队", description="新的简介"))
    assert set(answer["errors"]) == {"name"} and "description" in answer["saved"]
    team.refresh_from_db()
    assert (team.name, team.description) == ("自动保存队", "新的简介")


@pytest.mark.django_db
def test_a_chosen_logo_goes_up_at_once_and_only_once(team, client, settings, tmp_path):
    settings.MEDIA_ROOT = tmp_path
    url = reverse("team_manage", args=[team.pk])
    page = client.get(url).content.decode()
    assert "data-team-logo" in page and "还没有队标" in page
    images = get_image_model().objects.count()
    answer = _save(client, url, {**_profile(team), "logo_file": _png()})
    team.refresh_from_db()
    assert team.logo is not None and "logo_file" in answer["saved"]
    assert get_image_model().objects.count() == images + 1
    # The page shows it and empties the box, so it does not go up again.
    assert answer["values"] == {"logo_file": "", "remove_logo": False}
    assert re.search(r"<img[^>]+>", answer["replace"]["[data-team-logo]"])
    _save(client, url, _profile(team, description="只改了简介"))
    assert get_image_model().objects.count() == images + 1

    answer = _save(client, url, _profile(team, remove_logo="on"))
    team.refresh_from_db()
    assert team.logo is None and answer["values"]["remove_logo"] is False
    assert "还没有队标" in answer["replace"]["[data-team-logo]"]
