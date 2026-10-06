"""Round 216: the split page's edges (review S4, S5, S6, S8, S10).

A signup whose game ID was deleted, a player dragged into a role they have
no rank for, a generated split that leans on such a role, the two autosave
forms on the split page taking turns, and the back office scrim list asking
the database once per draft whether it may be deleted.
"""

import json
from datetime import timedelta
from pathlib import Path

import pytest
from django.conf import settings
from django.contrib.messages import get_messages
from django.core.management import call_command
from django.urls import reverse
from django.utils import timezone

from accounts.models import GameAccount
from accounts.tests.test_onboarding import _user
from core.tests.test_chapter15_audit import assert_no_n_plus_one
from scrims import services, teaming
from scrims.models import Role, Scrim, ScrimFormat, ScrimSignup, ScrimStatus
from scrims.tests.test_teaming import DIAMOND_3, add_player, fill, select_all

AUTOSAVE = {"HTTP_X_AUTOSAVE": "1", "HTTP_ACCEPT": "application/json"}


def _scrim(fmt=ScrimFormat.RQ_5V5, **kwargs):
    options = {
        "title": "216 内战",
        "starts_at": timezone.now() + timedelta(days=1),
        "format": fmt,
        "status": ScrimStatus.PUBLISHED,
    }
    options.update(kwargs)
    return Scrim.objects.create(**options)


@pytest.fixture
def site(db):
    call_command("init_site", verbosity=0)


@pytest.fixture
def manager(site, client):
    """A scrim manager, not a superuser (AGENTS「别只用超级管理员测权限」)."""
    user = _user("split216@example.com", "内战管理员")
    client.force_login(user)
    return user


# --- S4: a signup whose game ID is gone ---------------------------------------


@pytest.mark.django_db
def test_players_from_takes_a_signup_without_a_game_id():
    """216, S4: the game ID may be deleted once the scrim is over; the
    signup keeps no account and reading its battletag raised."""
    scrim = _scrim()
    signup = add_player(scrim, 0, [Role.TANK], {Role.TANK: DIAMOND_3})
    ScrimSignup.objects.filter(pk=signup.pk).update(game_account=None)
    rows = list(
        ScrimSignup.objects.filter(pk=signup.pk).select_related("user", "game_account")
    )
    assert rows[0].game_account is None

    (player,) = teaming.players_from(rows, scrim)

    assert player.battletag == ""
    assert player.ratings == {}
    assert player.best == 0


# --- S5: a role without a rank counts 0 when saved ----------------------------


@pytest.fixture
def unranked_board(manager):
    """Nine all-rounders and one tank-only player (index 9), all selected."""
    scrim = _scrim()
    signups = fill(scrim, 9)
    tank_only = add_player(scrim, 9, [Role.TANK], {Role.TANK: DIAMOND_3})
    select_all(scrim)
    return scrim, signups, tank_only


def _teams_post(signups, tank_only):
    """Indexes 0-3 and the tank-only player on A, 4-8 on B; everyone tanks
    except the tank-only player, dragged into damage."""
    data = {"part": "teams"}
    for index, signup in enumerate(signups):
        data[f"team-{signup.pk}"] = "a" if index < 4 else "b"
        data[f"role-{signup.pk}"] = Role.TANK
    data[f"team-{tank_only.pk}"] = "a"
    data[f"role-{tank_only.pk}"] = Role.DAMAGE
    return data


@pytest.mark.django_db
def test_a_role_without_a_rank_is_saved_as_zero(unranked_board, client):
    """216, S5: dragged to a role they have no rank for, a player was stored
    with their best rank of another role, so the saved totals disagreed
    with the board and with the algorithm (both count 0)."""
    scrim, signups, tank_only = unranked_board
    url = reverse("scrim_split", args=[scrim.pk])

    response = client.post(url, _teams_post(signups, tank_only), **AUTOSAVE)

    assert response.status_code == 200
    tank_only.refresh_from_db()
    assert tank_only.team == "a" and tank_only.assigned_role == Role.DAMAGE
    assert tank_only.rating_used == 0
    # A rank they do have is still what counts.
    first = ScrimSignup.objects.get(pk=signups[0].pk)
    assert first.rating_used == DIAMOND_3


@pytest.mark.django_db
def test_the_teams_autosave_answers_with_the_saved_totals(unranked_board, client):
    """216, S5: the answer carries the totals as stored, so the page shows
    what was saved rather than what the script added up."""
    scrim, signups, tank_only = unranked_board
    url = reverse("scrim_split", args=[scrim.pk])

    answer = json.loads(
        client.post(url, _teams_post(signups, tank_only), **AUTOSAVE).content
    )

    # fill() gives index i the score DIAMOND_3 + i % 5 in every role.
    total_a = sum(DIAMOND_3 + i % 5 for i in range(4)) + 0
    total_b = sum(DIAMOND_3 + i % 5 for i in range(4, 9))
    replace = answer["replace"]
    assert replace["[data-total-a]"] == f"<strong data-total-a>{total_a}</strong>"
    assert replace["[data-total-b]"] == f"<strong data-total-b>{total_b}</strong>"
    gap = abs(total_a - total_b)
    assert replace["[data-gap]"] == f"<strong data-gap>{gap}</strong>"
    assert (
        replace['[data-team-total="a"]']
        == f'<span data-team-total="a">{total_a}</span>'
    )
    assert (
        replace['[data-team-total="b"]']
        == f'<span data-team-total="b">{total_b}</span>'
    )


# --- S6: a generated split that leans on an unranked role ---------------------


def test_unrated_placements_names_who_plays_a_role_without_a_rank():
    """216, S6: listed as 「昵称（位置）」, only for role-queue formats."""
    players = [
        teaming.Player(1, "甲", "A#1", ("tank", "damage"), {"damage": 20}, 20),
        teaming.Player(2, "乙", "B#2", ("tank",), {"tank": 20}, 20),
        teaming.Player(3, "丙", "C#3", ("support",), {"support": 20}, 20),
    ]
    split = teaming.Split(
        a=teaming.Assignment(
            by_role={"tank": (1,), "support": (3,)}, total=20, role_totals={}
        ),
        b=teaming.Assignment(by_role={"tank": (2,)}, total=20, role_totals={}),
        score=(0, 0),
    )

    assert teaming.unrated_placements(
        split, players, Scrim(format=ScrimFormat.RQ_5V5)
    ) == ["甲（坦克）"]
    assert (
        teaming.unrated_placements(split, players, Scrim(format=ScrimFormat.OPEN_5V5))
        == []
    )


@pytest.mark.django_db
def test_generating_warns_about_a_role_counted_as_zero(manager, client):
    """216, S6: only two players can tank and one of them lost the tank
    rank after signing up, so every legal split puts them there at 0. The
    admin is told instead of finding out from a lopsided game."""
    scrim = _scrim()
    lost = add_player(
        scrim,
        0,
        [Role.TANK, Role.DAMAGE],
        {Role.TANK: DIAMOND_3, Role.DAMAGE: DIAMOND_3},
    )
    GameAccount.objects.filter(pk=lost.game_account_id).update(rank_tank=None)
    add_player(scrim, 1, [Role.TANK], {Role.TANK: DIAMOND_3})
    for index in range(2, 6):
        add_player(scrim, index, [Role.DAMAGE], {Role.DAMAGE: DIAMOND_3})
    for index in range(6, 10):
        add_player(scrim, index, [Role.SUPPORT], {Role.SUPPORT: DIAMOND_3})

    response = client.post(
        reverse("scrim_split", args=[scrim.pk]),
        {
            "action": "generate",
            "signups": list(scrim.signups.values_list("pk", flat=True)),
        },
    )

    assert response.status_code == 302
    lost.refresh_from_db()
    assert lost.assigned_role == Role.TANK and lost.rating_used == 0
    texts = [str(message) for message in get_messages(response.wsgi_request)]
    warning = [text for text in texts if "按 0 分算" in text]
    assert warning, texts
    assert "玩家0（坦克）" in warning[0]


@pytest.mark.django_db
def test_generating_with_every_role_ranked_gives_no_warning(manager, client):
    """The other side of S6: nothing to say, nothing said."""
    scrim = _scrim()
    signups = fill(scrim, 10)

    response = client.post(
        reverse("scrim_split", args=[scrim.pk]),
        {"action": "generate", "signups": [row.pk for row in signups]},
    )

    texts = [str(message) for message in get_messages(response.wsgi_request)]
    assert any("已生成分队" in text for text in texts)
    assert not any("按 0 分算" in text for text in texts)


# --- S8: the two forms on the split page take turns ---------------------------


def _read(relative):
    return (Path(settings.BASE_DIR) / relative).read_text(encoding="utf-8")


def test_both_split_forms_share_one_autosave_queue():
    """216, S8: the tick list answers with a whole new board holding the
    teams form; a move saved at the same moment was overwritten. Both forms
    name the same queue. (A substring guard: the behaviour is browser-side.)"""
    page = _read("scrims/templates/scrims/admin/split.html")
    board = _read("scrims/templates/scrims/admin/_board.html")
    pick_form = page.split("data-split-form", 1)[1].split(">", 1)[0]
    teams_form = board.split("data-teams-form", 1)[1].split(">", 1)[0]
    assert 'data-autosave-queue="split"' in pick_form
    assert 'data-autosave-queue="split"' in teams_form


def test_a_save_waits_for_another_form_in_its_queue():
    """216, S8: ``save`` asks ``queuedBehind`` before it posts, and waits
    for that save to finish."""
    source = _read("static/js/autosave.js")
    assert "Saver.prototype.queuedBehind = function" in source
    queued = source.split("Saver.prototype.queuedBehind = function", 1)[1]
    queued = queued.split("Saver.prototype.", 1)[0]
    assert 'getAttribute("data-autosave-queue")' in queued
    save = source.split("Saver.prototype.save = function", 1)[1]
    before_post = save.split(".fetch(", 1)[0]
    assert "this.queuedBehind()" in before_post
    assert "ahead.then(" in before_post


# --- S10: the back office list and can_delete ---------------------------------


@pytest.mark.django_db
def test_the_back_office_scrim_list_is_flat_in_drafts(manager, client):
    """216, S10: ``can_delete`` asked the database once per draft on the
    page; the list already counts signups."""
    starts = timezone.now() + timedelta(days=3)

    def seed(count):
        for _ in range(count):
            Scrim.objects.create(
                title=f"草稿 216-{Scrim.objects.count()}",
                starts_at=starts,
                format=ScrimFormat.RQ_5V5,
                status=ScrimStatus.DRAFT,
            )

    assert_no_n_plus_one(client, reverse("scrims:index"), seed)
    listing = client.get(reverse("scrims:index")).content.decode()
    some = Scrim.objects.filter(status=ScrimStatus.DRAFT).first()
    assert reverse("scrims:delete", args=[some.pk]) in listing


@pytest.mark.django_db
def test_can_delete_reads_the_counted_signups(django_assert_num_queries):
    """216, S10: with ``signup_total`` on the row, no query is made."""
    from django.db.models import Count

    empty = _scrim(status=ScrimStatus.DRAFT)
    taken = _scrim()  # a draft takes no signups; signed up, then set back
    add_player(taken, 0, [Role.TANK], {Role.TANK: DIAMOND_3})
    Scrim.objects.filter(pk=taken.pk).update(status=ScrimStatus.DRAFT)
    rows = {
        row.pk: row
        for row in Scrim.objects.annotate(signup_total=Count("signups")).filter(
            pk__in=[empty.pk, taken.pk]
        )
    }

    with django_assert_num_queries(0):
        assert services.can_delete(rows[empty.pk]) is True
        assert services.can_delete(rows[taken.pk]) is False

    # Without the count it still asks, and still answers right.
    assert services.can_delete(Scrim.objects.get(pk=empty.pk)) is True
    assert services.can_delete(Scrim.objects.get(pk=taken.pk)) is False
