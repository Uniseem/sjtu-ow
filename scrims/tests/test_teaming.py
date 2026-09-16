"""Design 9.3-9.6: selection, the split algorithm, adjustment, copy text."""

import random
import time
from datetime import timedelta
from itertools import combinations

import pytest
from django.utils import timezone

from accounts.models import ContactMethod, ContactType, GameAccount, User
from scrims import services, teaming
from scrims.models import (
    ROLE_REQUIREMENTS,
    Role,
    Scrim,
    ScrimFormat,
    ScrimStatus,
)

# Appendix A scores used in the fixtures.
BRONZE_5, GOLD_3, PLATINUM_1, DIAMOND_3, MASTER_5 = 1, 12, 18, 22, 26


def make_scrim(fmt=ScrimFormat.RQ_5V5, **kwargs):
    now = timezone.now()
    options = {
        "title": "周五内战",
        "starts_at": now + timedelta(days=1),
        "format": fmt,
        "status": ScrimStatus.PUBLISHED,
    }
    options.update(kwargs)
    return Scrim.objects.create(**options)


def add_player(scrim, index, roles, ratings):
    """One signed-up player with exactly these role ranks."""
    now = timezone.now()
    user = User.objects.create_user(
        email=f"p{index}@example.com",
        password="Correct-Horse-Battery-1",
        nickname=f"玩家{index}",
        is_sjtu=True,
        agreed_terms_at=now,
        agreed_cross_border_at=now,
    )
    account = GameAccount.objects.create(
        user=user,
        battletag=f"Player{index}#{1000 + index}",
        rank_tank=ratings.get(Role.TANK),
        rank_damage=ratings.get(Role.DAMAGE),
        rank_support=ratings.get(Role.SUPPORT),
    )
    ContactMethod.objects.create(user=user, type=ContactType.QQ, value="123456789")
    return services.sign_up(
        scrim=scrim, user=user, game_account_id=account.pk, roles=list(roles)
    )


def fill(scrim, count, *, roles=None, score=DIAMOND_3, vary=True):
    """`count` players who can all play everything unless told otherwise."""
    roles = roles or [Role.TANK, Role.DAMAGE, Role.SUPPORT]
    signups = []
    for index in range(count):
        value = score + (index % 5) if vary else score
        signups.append(add_player(scrim, index, roles, {role: value for role in roles}))
    return signups


def select_all(scrim):
    services.set_selection(
        scrim=scrim, signup_ids=[row.pk for row in scrim.signups.all()]
    )


# --- the algorithm -------------------------------------------------------------


@pytest.mark.django_db
def test_role_queue_5v5_respects_the_requirements():
    scrim = make_scrim(ScrimFormat.RQ_5V5)
    fill(scrim, 10)
    select_all(scrim)

    split, players = services.generate_teams(scrim)

    wanted = ROLE_REQUIREMENTS[ScrimFormat.RQ_5V5]
    for assignment in (split.a, split.b):
        for role, needed in wanted.items():
            assert len(assignment.by_role[role]) == needed
    assert sum(len(ids) for ids in split.a.by_role.values()) == 5
    assert sum(len(ids) for ids in split.b.by_role.values()) == 5


@pytest.mark.django_db
def test_role_queue_6v6_respects_the_requirements():
    scrim = make_scrim(ScrimFormat.RQ_6V6)
    fill(scrim, 12)
    select_all(scrim)

    split, players = services.generate_teams(scrim)

    wanted = ROLE_REQUIREMENTS[ScrimFormat.RQ_6V6]
    for assignment in (split.a, split.b):
        for role, needed in wanted.items():
            assert len(assignment.by_role[role]) == needed


@pytest.mark.django_db
def test_nobody_is_placed_in_a_role_they_cannot_play():
    scrim = make_scrim(ScrimFormat.RQ_5V5)
    # Two tank-only players, the rest flexible.
    add_player(scrim, 0, [Role.TANK], {Role.TANK: DIAMOND_3})
    add_player(scrim, 1, [Role.TANK], {Role.TANK: GOLD_3})
    for index in range(2, 10):
        add_player(
            scrim,
            index,
            [Role.DAMAGE, Role.SUPPORT],
            {Role.DAMAGE: DIAMOND_3 + index % 3, Role.SUPPORT: PLATINUM_1},
        )
    select_all(scrim)

    split, players = services.generate_teams(scrim)

    by_id = {player.signup_id: player for player in players}
    for assignment in (split.a, split.b):
        for role, ids in assignment.by_role.items():
            for signup_id in ids:
                assert role in by_id[signup_id].roles


@pytest.mark.django_db
def test_a_perfectly_balanced_field_splits_evenly():
    scrim = make_scrim(ScrimFormat.RQ_5V5)
    fill(scrim, 10, score=DIAMOND_3, vary=False)
    select_all(scrim)

    split, _ = services.generate_teams(scrim)

    assert split.score == (0, 0)
    assert split.a.total == split.b.total


def brute_force_best(players, fmt):
    """Every split, every assignment pair, no pruning and no dedupe."""
    requirements = ROLE_REQUIREMENTS[fmt]
    first, rest = players[0], players[1:]
    size = len(players) // 2
    best = None
    for others in combinations(rest, size - 1):
        team_a = (first, *others)
        team_b = tuple(player for player in rest if player not in others)
        side_a = teaming._assignments(team_a, requirements)
        side_b = teaming._assignments(team_b, requirements)
        if not side_a or not side_b:
            continue
        for a in side_a:
            for b in side_b:
                score = teaming._score(a, b)
                if best is None or score < best:
                    best = score
    return best


@pytest.mark.django_db
@pytest.mark.parametrize("seed", [1, 2, 3, 5, 7, 11, 13, 17])
def test_the_split_matches_brute_force(seed):
    """The pruned search must find the same optimum as an exhaustive one.

    One seed is not enough: an over-aggressive prune still happens to find
    the optimum on friendly data, so this sweeps several fields.
    """
    scrim = make_scrim(ScrimFormat.RQ_5V5)
    rng = random.Random(seed)
    for index in range(10):
        roles = [Role.TANK, Role.DAMAGE, Role.SUPPORT]
        picked = rng.sample(roles, rng.choice([2, 3]))
        add_player(scrim, index, picked, {role: rng.randint(5, 30) for role in picked})
    select_all(scrim)
    players = teaming.players_from(services.selected_signups(scrim), scrim)

    try:
        best = teaming.generate(players, scrim).score
    except teaming.NoSolution:
        assert brute_force_best(players, ScrimFormat.RQ_5V5) is None
        return

    assert best == brute_force_best(players, ScrimFormat.RQ_5V5)


@pytest.mark.django_db
def test_the_score_compares_total_gap_before_role_gap():
    a = teaming.Assignment(
        by_role={}, total=100, role_totals={Role.TANK: 50, Role.DAMAGE: 50}
    )
    close_total_wide_roles = teaming.Assignment(
        by_role={}, total=100, role_totals={Role.TANK: 10, Role.DAMAGE: 90}
    )
    far_total_even_roles = teaming.Assignment(
        by_role={}, total=120, role_totals={Role.TANK: 60, Role.DAMAGE: 60}
    )

    assert teaming._score(a, close_total_wide_roles) == (0, 80)
    assert teaming._score(a, far_total_even_roles) == (20, 20)
    # Total gap wins even though the role gap is far worse.
    assert teaming._score(a, close_total_wide_roles) < teaming._score(
        a, far_total_even_roles
    )


def test_the_pairing_search_keeps_looking_past_the_first_equal_total():
    """The walk must not stop at the first candidate with the same total.

    Both B options tie on total, so only the role gap separates them. A
    prune that examined just the nearest total would settle for the worse
    one, and nothing about the team totals would look wrong.
    """
    a = teaming.Assignment(
        by_role={},
        total=100,
        role_totals={Role.TANK: 20, Role.DAMAGE: 40, Role.SUPPORT: 40},
    )
    lopsided = teaming.Assignment(
        by_role={},
        total=100,
        role_totals={Role.TANK: 50, Role.DAMAGE: 25, Role.SUPPORT: 25},
    )
    matched = teaming.Assignment(
        by_role={},
        total=100,
        role_totals={Role.TANK: 20, Role.DAMAGE: 40, Role.SUPPORT: 40},
    )

    pair, score = teaming._best_pairing([a], [lopsided, matched])

    assert score == (0, 0)
    assert pair[1] is matched


@pytest.mark.django_db
def test_open_format_ignores_roles_and_uses_the_best_rank():
    """Five players at 22 and five at 12 total 170, which two teams of five
    cannot split evenly, so 90/80 is the real optimum."""
    scrim = make_scrim(ScrimFormat.OPEN_5V5)
    for index in range(10):
        add_player(
            scrim,
            index,
            [Role.DAMAGE],
            {Role.DAMAGE: DIAMOND_3 if index < 5 else GOLD_3},
        )
    select_all(scrim)

    split, _ = services.generate_teams(scrim)

    assert split.a.total + split.b.total == 5 * DIAMOND_3 + 5 * GOLD_3
    assert abs(split.a.total - split.b.total) == 10
    assert split.score == (10, 0)
    assert set(split.a.by_role) == {""}  # no roles assigned


@pytest.mark.django_db
def test_open_format_splits_an_even_field_evenly():
    scrim = make_scrim(ScrimFormat.OPEN_5V5)
    for index in range(10):
        add_player(scrim, index, [Role.DAMAGE], {Role.DAMAGE: DIAMOND_3})
    select_all(scrim)

    split, _ = services.generate_teams(scrim)

    assert split.a.total == split.b.total
    assert split.score == (0, 0)


@pytest.mark.django_db
def test_regenerating_can_give_a_different_equivalent_split():
    """Design 9.4: ties are broken at random, so a retry may differ.

    What varies is who ends up on which team. Within one team the role
    assignment is deterministic, because design 9.4's dedupe step collapses
    assignments that score identically -- with identical players that is all
    of them.
    """
    scrim = make_scrim(ScrimFormat.RQ_5V5)
    fill(scrim, 10, score=DIAMOND_3, vary=False)
    select_all(scrim)

    seen = set()
    for seed in range(12):
        split, _ = services.generate_teams(scrim, rng=random.Random(seed))
        assert split.score == (0, 0)
        members = tuple(
            sorted(signup_id for ids in split.a.by_role.values() for signup_id in ids)
        )
        seen.add(members)

    assert len(seen) > 1


# --- no solution ---------------------------------------------------------------


@pytest.mark.django_db
def test_not_enough_tanks_says_so():
    scrim = make_scrim(ScrimFormat.RQ_6V6)
    add_player(scrim, 0, [Role.TANK], {Role.TANK: DIAMOND_3})
    for index in range(1, 12):
        add_player(
            scrim,
            index,
            [Role.DAMAGE, Role.SUPPORT],
            {Role.DAMAGE: DIAMOND_3, Role.SUPPORT: PLATINUM_1},
        )
    select_all(scrim)

    with pytest.raises(teaming.NoSolution) as caught:
        services.generate_teams(scrim)

    message = str(caught.value)
    assert "坦克" in message
    assert "1 人" in message
    assert "4 人" in message  # 6v6 needs two per team


@pytest.mark.django_db
def test_the_wrong_number_of_players_says_so():
    scrim = make_scrim(ScrimFormat.RQ_5V5)
    fill(scrim, 8)
    select_all(scrim)

    with pytest.raises(teaming.NoSolution, match="正好 10 人"):
        services.generate_teams(scrim)


@pytest.mark.django_db
def test_a_field_with_no_legal_assignment_says_so():
    """Enough tank-capable players overall, but not spread across two teams."""
    scrim = make_scrim(ScrimFormat.RQ_5V5)
    # Everyone can tank, but only two people can play damage at all.
    for index in range(2):
        add_player(
            scrim,
            index,
            [Role.TANK, Role.DAMAGE],
            {Role.TANK: DIAMOND_3, Role.DAMAGE: DIAMOND_3},
        )
    for index in range(2, 10):
        add_player(
            scrim,
            index,
            [Role.TANK, Role.SUPPORT],
            {Role.TANK: DIAMOND_3, Role.SUPPORT: PLATINUM_1},
        )
    select_all(scrim)

    with pytest.raises(teaming.NoSolution) as caught:
        services.generate_teams(scrim)

    assert "输出" in str(caught.value)


# --- performance ---------------------------------------------------------------


@pytest.mark.django_db
def test_6v6_finishes_within_a_second():
    """Design 9.4 and the M6 acceptance bar. Worst case: everyone plays all."""
    scrim = make_scrim(ScrimFormat.RQ_6V6)
    rng = random.Random(3)
    for index in range(12):
        roles = [Role.TANK, Role.DAMAGE, Role.SUPPORT]
        add_player(scrim, index, roles, {role: rng.randint(5, 35) for role in roles})
    select_all(scrim)
    signups = services.selected_signups(scrim)
    players = teaming.players_from(signups, scrim)

    started = time.perf_counter()
    teaming.generate(players, scrim)
    elapsed = time.perf_counter() - started

    assert elapsed < 1.0, f"6v6 分队用了 {elapsed:.2f} 秒"


# --- selection and saving ------------------------------------------------------


@pytest.mark.django_db
def test_selection_clears_the_placement_of_anyone_unticked():
    scrim = make_scrim(ScrimFormat.RQ_5V5)
    fill(scrim, 10)
    select_all(scrim)
    split, players = services.generate_teams(scrim)
    services.save_teams(
        scrim=scrim, placements=services.placements_from_split(split, players, scrim)
    )
    dropped = scrim.signups.first()
    assert dropped.team

    keep = [row.pk for row in scrim.signups.all() if row.pk != dropped.pk]
    services.set_selection(scrim=scrim, signup_ids=keep)

    dropped.refresh_from_db()
    assert dropped.is_selected is False
    assert dropped.team == ""
    assert dropped.rating_used is None


@pytest.mark.django_db
def test_saving_records_the_rating_used_and_stamps_the_time():
    scrim = make_scrim(ScrimFormat.RQ_5V5)
    fill(scrim, 10)
    select_all(scrim)
    split, players = services.generate_teams(scrim)

    services.save_teams(
        scrim=scrim, placements=services.placements_from_split(split, players, scrim)
    )

    scrim.refresh_from_db()
    assert scrim.teams_generated_at is not None
    placed = scrim.signups.filter(team__in=["a", "b"])
    assert placed.count() == 10
    for signup in placed:
        assert signup.assigned_role in Role.values
        assert signup.rating_used == signup.rating_for(signup.assigned_role)


@pytest.mark.django_db
def test_saving_a_split_that_breaks_the_format_is_allowed():
    """Design 9.5: flag it, but let the admin save anyway."""
    scrim = make_scrim(ScrimFormat.RQ_5V5)
    signups = fill(scrim, 10)
    select_all(scrim)

    # Everyone on A as a tank: wildly illegal, but it must save.
    placements = {row.pk: ("a", Role.TANK, DIAMOND_3) for row in signups}
    services.save_teams(scrim=scrim, placements=placements)

    rows = services.team_rows(scrim)
    assert len(rows["a"]) == 10
    assert rows["b"] == []
    problems = services.requirement_problems(scrim, rows["a"])
    assert problems  # flagged
    assert any("坦克" in problem for problem in problems)


@pytest.mark.django_db
def test_saving_clears_the_stale_flag():
    scrim = make_scrim(ScrimFormat.RQ_5V5)
    fill(scrim, 10)
    select_all(scrim)
    split, players = services.generate_teams(scrim)
    services.save_teams(
        scrim=scrim, placements=services.placements_from_split(split, players, scrim)
    )
    Scrim.objects.filter(pk=scrim.pk).update(roster_changed_at=timezone.now())
    scrim.refresh_from_db()
    assert services.teams_are_stale(scrim) is True

    services.save_teams(
        scrim=scrim, placements=services.placements_from_split(split, players, scrim)
    )

    scrim.refresh_from_db()
    assert services.teams_are_stale(scrim) is False


# --- copy text -----------------------------------------------------------------


@pytest.mark.django_db
def test_the_copy_text_matches_the_designs_format():
    """Design 9.6, compared line by line."""
    scrim = make_scrim(
        ScrimFormat.RQ_5V5,
        title="周五内战",
        starts_at=timezone.make_aware(
            timezone.datetime(2026, 10, 9, 20, 0), timezone.get_current_timezone()
        ),
    )
    people = [
        ("玩家甲", Role.TANK, DIAMOND_3),
        ("玩家乙", Role.DAMAGE, MASTER_5),
        ("玩家丙", Role.DAMAGE, DIAMOND_3),
        ("玩家丁", Role.SUPPORT, DIAMOND_3),
        ("玩家戊", Role.SUPPORT, PLATINUM_1),
    ]
    placements = {}
    for team in ("a", "b"):
        for index, (name, role, score) in enumerate(people):
            signup = add_player(
                scrim,
                index if team == "a" else index + 5,
                [role],
                {role: score},
            )
            signup.user.nickname = f"{name}{'' if team == 'a' else '二'}"
            signup.user.save(update_fields=["nickname"])
            placements[signup.pk] = (team, role, score)
    services.save_teams(scrim=scrim, placements=placements)

    text = services.copy_text(scrim)
    lines = text.split("\n")

    assert lines[0] == "【周五内战】2026-10-09 20:00 · 角色限定 5v5"
    assert lines[1] == ""
    assert lines[2].startswith("A 队（总分 ")
    assert lines[3].startswith("坦克：玩家甲 Player0#1000 钻石 3")
    assert " / " in lines[4]  # two damage players on one line
    assert lines[4].startswith("输出：")
    assert lines[5].startswith("支援：")
    assert "B 队（总分 " in text
    # Design 9.6: game IDs are included on purpose.
    assert "Player0#1000" in text


@pytest.mark.django_db
def test_the_copy_text_for_an_open_format_has_no_roles():
    scrim = make_scrim(ScrimFormat.OPEN_5V5)
    signups = fill(scrim, 10, roles=[Role.DAMAGE])
    select_all(scrim)
    placements = {
        row.pk: ("a" if index < 5 else "b", "", row.best_rating)
        for index, row in enumerate(signups)
    }
    services.save_teams(scrim=scrim, placements=placements)

    text = services.copy_text(scrim)

    assert "坦克：" not in text
    assert "输出：" not in text
    assert "A 队（总分 " in text


# --- the admin page ------------------------------------------------------------


@pytest.mark.django_db
def test_the_split_page_needs_permission(client, db):
    scrim = make_scrim()
    now = timezone.now()
    plain = User.objects.create_user(
        email="plain@example.com",
        password="Correct-Horse-Battery-1",
        nickname="路人",
        agreed_terms_at=now,
        agreed_cross_border_at=now,
    )
    client.force_login(plain)

    response = client.get(f"/admin/scrims/{scrim.pk}/split/")

    assert response.status_code in (302, 403)
    assert b"\xe5\x88\x86\xe9\x98\x9f\xe7\xbb\x93\xe6\x9e\x9c" not in response.content


@pytest.mark.django_db
def test_a_superuser_can_generate_and_save_from_the_page(client, db):
    scrim = make_scrim(ScrimFormat.RQ_5V5)
    signups = fill(scrim, 10)
    admin = User.objects.create_superuser(
        email="root@example.com", password="Correct-Horse-Battery-1", nickname="超管"
    )
    client.force_login(admin)

    response = client.post(
        f"/admin/scrims/{scrim.pk}/split/",
        {"action": "generate", "signups": [row.pk for row in signups]},
    )

    assert response.status_code == 302
    scrim.refresh_from_db()
    assert scrim.teams_generated_at is not None
    assert scrim.signups.filter(team="a").count() == 5
    assert scrim.signups.filter(team="b").count() == 5

    page = client.get(f"/admin/scrims/{scrim.pk}/split/")
    assert page.status_code == 200
    assert "分队结果" in page.content.decode()


@pytest.mark.django_db
def test_the_split_page_uses_no_alpine_expressions(client, db):
    """020's lesson: the site ships Alpine's CSP build."""
    scrim = make_scrim(ScrimFormat.RQ_5V5)
    fill(scrim, 10)
    admin = User.objects.create_superuser(
        email="root2@example.com", password="Correct-Horse-Battery-1", nickname="超管"
    )
    client.force_login(admin)

    html = client.get(f"/admin/scrims/{scrim.pk}/split/").content.decode()

    for attribute in ("x-data", "x-on:", "x-ref", "@click", "onclick="):
        assert attribute not in html, attribute


@pytest.mark.django_db
def test_the_plain_text_endpoint(client, db):
    scrim = make_scrim(ScrimFormat.RQ_5V5)
    fill(scrim, 10)
    select_all(scrim)
    split, players = services.generate_teams(scrim)
    services.save_teams(
        scrim=scrim, placements=services.placements_from_split(split, players, scrim)
    )
    admin = User.objects.create_superuser(
        email="root3@example.com", password="Correct-Horse-Battery-1", nickname="超管"
    )
    client.force_login(admin)

    response = client.get(f"/admin/scrims/{scrim.pk}/split/text/")

    assert response.status_code == 200
    assert response["Content-Type"].startswith("text/plain")
    assert "A 队（总分 " in response.content.decode()
