"""217 复核 06 内战：复现脚本（只读业务代码，不改）。

在测试机上跑：
    bash scripts/remote-check.sh run uv run pytest -q -s \
        handoff/rounds/217-second-review/findings/06-repro_scrims.py

除了 6v6 暴力对照（断言「算法 == 暴力」：绿 = 没问题），每条 test 断言的是
「问题存在」：绿 = 复现了。
"""

import json
import random
import time
from datetime import timedelta
from itertools import combinations
from types import SimpleNamespace

import pytest
from django.urls import reverse
from django.utils import timezone

from accounts.models import GameAccount
from backoffice.forms import ScrimForm
from scrims import services, teaming
from scrims.models import (
    ROLE_REQUIREMENTS,
    Role,
    Scrim,
    ScrimFormat,
    ScrimSignup,
    ScrimStatus,
)
from scrims.tests.test_216_split_edges import manager, site  # noqa: F401
from scrims.tests.test_teaming import (
    DIAMOND_3,
    GOLD_3,
    MASTER_4,
    PLATINUM_2,
    add_player,
    fill,
    make_scrim,
    select_all,
)

AUTOSAVE = {"HTTP_X_AUTOSAVE": "1", "HTTP_ACCEPT": "application/json"}


def _generate_and_save(scrim):
    split, players = services.generate_teams(scrim, rng=random.Random(1))
    services.save_teams(
        scrim=scrim, placements=services.placements_from_split(split, players, scrim)
    )
    return split


def _board_post(scrim):
    """What the teams form on the page holds right now (hidden inputs)."""
    data = {"part": "teams"}
    for row in scrim.signups.all():
        if row.team:
            data[f"team-{row.pk}"] = row.team
            data[f"role-{row.pk}"] = row.assigned_role
    return data


# --- 06-1 不限位置：最高分只看勾了的位置，不看游戏 ID 上全部段位 -----------------


@pytest.mark.django_db
def test_open_format_best_ignores_ranks_of_unticked_roles():
    scrim = make_scrim(ScrimFormat.OPEN_5V5)
    # 只勾坦克，坦克没段位；输出是大师 4。报名规则（至少一个位置有段位）放行。
    star = add_player(scrim, 0, [Role.TANK], {Role.DAMAGE: MASTER_4})
    # 只勾支援（白金 2），输出是大师 4。
    flex = add_player(
        scrim, 1, [Role.SUPPORT], {Role.SUPPORT: PLATINUM_2, Role.DAMAGE: MASTER_4}
    )
    for index in range(2, 10):
        add_player(scrim, index, [Role.DAMAGE], {Role.DAMAGE: GOLD_3})
    print("star.best_rating =", star.best_rating, "（设计 9.4 应为", MASTER_4, "）")
    print("flex.best_rating =", flex.best_rating, "（设计 9.4 应为", MASTER_4, "）")
    assert star.best_rating is None
    assert flex.best_rating == PLATINUM_2

    select_all(scrim)
    _generate_and_save(scrim)
    star.refresh_from_db()
    text = services.copy_text(scrim)
    print(text)
    assert star.rating_used == 0
    line = next(line for line in text.splitlines() if line.startswith("玩家0 "))
    assert line.endswith("青铜 5")  # 大师 4 的人在群里被写成青铜 5


# --- 06-2 没段位的位置按 0 分算，复制文字写「青铜 5」，卡片写「—」 -------------


@pytest.mark.django_db
def test_unranked_placement_reads_bronze_five_in_copy_text(manager, client):
    scrim = make_scrim(ScrimFormat.RQ_5V5)
    signups = fill(scrim, 9)
    tank_only = add_player(scrim, 9, [Role.TANK], {Role.TANK: DIAMOND_3})
    select_all(scrim)
    data = {"part": "teams"}
    for index, signup in enumerate(signups):
        data[f"team-{signup.pk}"] = "a" if index < 4 else "b"
        data[f"role-{signup.pk}"] = Role.TANK
    data[f"team-{tank_only.pk}"] = "a"
    data[f"role-{tank_only.pk}"] = Role.DAMAGE
    url = reverse("scrim_split", args=[scrim.pk])
    assert client.post(url, data, **AUTOSAVE).status_code == 200
    text = services.copy_text(scrim)
    print(text)
    damage = next(line for line in text.splitlines() if line.startswith("输出："))
    assert "玩家9 Player9#1009 青铜 5" in damage
    page = client.get(url).content.decode()
    card = page.split(f'data-signup="{tank_only.pk}"', 1)[1].split("</li>", 1)[0]
    assert "data-card-rank>—<" in card


# --- 06-3 拖到一个没勾、但游戏 ID 上有段位的位置：存段位，板子算 0 ------------


@pytest.mark.django_db
def test_unticked_role_with_a_rank_is_stored_but_board_counts_zero(manager, client):
    scrim = make_scrim(ScrimFormat.RQ_5V5)
    signups = fill(scrim, 9)
    # 只报坦克，但这个游戏 ID 的输出是大师 4。
    tanker = add_player(
        scrim, 9, [Role.TANK], {Role.TANK: DIAMOND_3, Role.DAMAGE: MASTER_4}
    )
    select_all(scrim)
    data = {"part": "teams"}
    for index, signup in enumerate(signups):
        data[f"team-{signup.pk}"] = "a" if index < 4 else "b"
        data[f"role-{signup.pk}"] = Role.TANK
    data[f"team-{tanker.pk}"] = "a"
    data[f"role-{tanker.pk}"] = Role.DAMAGE
    url = reverse("scrim_split", args=[scrim.pk])
    answer = json.loads(client.post(url, data, **AUTOSAVE).content)
    tanker.refresh_from_db()
    print("rating_used =", tanker.rating_used, "rating_map =", tanker.rating_map)
    print("server total a:", answer["replace"]["[data-total-a]"])
    assert tanker.rating_used == MASTER_4  # 服务器存了大师 4
    assert "damage" not in json.loads(tanker.rating_map)  # 脚本 ratingFor → 0


# --- 06-4 打开着的旧板子把「改了位置、已移出」的人原样放回去，并清掉提示 ----------


@pytest.mark.django_db
def test_stale_board_puts_back_a_player_who_changed_roles(manager, client):
    scrim = make_scrim(ScrimFormat.RQ_5V5)
    fill(scrim, 10)
    select_all(scrim)
    _generate_and_save(scrim)
    stale_board = _board_post(scrim)  # 管理员这时打开着分队页

    tank = scrim.signups.filter(assigned_role=Role.TANK).first()
    old_team = tank.team
    # 这名坦克截止前改成只打支援（213/S2：移出分队并标记）
    services.sign_up(
        scrim=scrim,
        user=tank.user,
        game_account_id=tank.game_account_id,
        roles=[Role.SUPPORT],
    )
    scrim.refresh_from_db()
    tank.refresh_from_db()
    assert tank.team == "" and not tank.is_selected
    assert services.teams_are_stale(scrim)

    # 管理员在旧板子上拖了别的人一下（任意一次移动都 POST 整张板子）
    url = reverse("scrim_split", args=[scrim.pk])
    assert client.post(url, stale_board, **AUTOSAVE).status_code == 200

    tank.refresh_from_db()
    scrim.refresh_from_db()
    print("after:", tank.team, tank.assigned_role, tank.is_selected, tank.roles)
    assert tank.team == old_team
    assert tank.assigned_role == Role.TANK and Role.TANK not in tank.roles
    assert tank.is_selected
    assert not services.teams_are_stale(scrim)  # 「分队有变化」也没了
    assert f"{tank.user.nickname} " in services.copy_text(scrim)


@pytest.mark.django_db
def test_stale_pick_list_reselects_a_player_who_changed_id(manager, client):
    scrim = make_scrim(ScrimFormat.RQ_5V5)
    signups = fill(scrim, 11)
    services.set_selection(scrim=scrim, signup_ids=[row.pk for row in signups[:10]])
    stale_ticks = [row.pk for row in signups[:10]]
    mover = signups[0]
    second = GameAccount.objects.create(
        user=mover.user,
        battletag="Second#1",
        rank_tank=DIAMOND_3,
        rank_damage=DIAMOND_3,
        rank_support=DIAMOND_3,
    )
    services.sign_up(
        scrim=scrim,
        user=mover.user,
        game_account_id=second.pk,
        roles=mover.roles,
    )
    mover.refresh_from_db()
    assert not mover.is_selected
    url = reverse("scrim_split", args=[scrim.pk])
    # 旧页面上勾第 11 个人：整张勾选表（含已移出的人）一起 POST
    client.post(
        url, {"part": "pick", "signups": [*stale_ticks, signups[10].pk]}, **AUTOSAVE
    )
    mover.refresh_from_db()
    assert mover.is_selected


# --- 06-5 改规格（开放 → 角色限定）后：复制文字只剩总分，没有人，也不提示 -----


@pytest.mark.django_db
def test_format_change_after_split_drops_everyone_from_copy_text():
    scrim = make_scrim(ScrimFormat.OPEN_5V5)
    fill(scrim, 10)
    select_all(scrim)
    _generate_and_save(scrim)
    local = timezone.localtime(scrim.starts_at)
    form = ScrimForm(
        {
            "title": scrim.title,
            "description": "",
            "starts_at": local.strftime("%Y-%m-%dT%H:%M"),
            "signup_closes_at": "",
            "format": ScrimFormat.RQ_5V5,
        },
        instance=scrim,
    )
    assert form.is_valid(), form.errors
    form.save()
    scrim.refresh_from_db()
    text = services.copy_text(scrim)
    print(text)
    assert "A 队（总分 " in text
    assert "玩家" not in text  # 十个人都在队里、都算进总分，复制文字里一个也没有
    assert not services.teams_are_stale(scrim)


# --- 06-6 报名截止可以晚于开始：开始以后还能报名、改、取消 ---------------------


@pytest.mark.django_db
def test_signup_deadline_after_start_is_accepted():
    scrim = make_scrim(ScrimFormat.RQ_5V5)
    start = timezone.localtime(scrim.starts_at)
    form = ScrimForm(
        {
            "title": scrim.title,
            "description": "",
            "starts_at": start.strftime("%Y-%m-%dT%H:%M"),
            "signup_closes_at": (start + timedelta(hours=5)).strftime("%Y-%m-%dT%H:%M"),
            "format": ScrimFormat.RQ_5V5,
        },
        instance=scrim,
    )
    assert form.is_valid(), form.errors
    form.save()
    scrim.refresh_from_db()
    late = scrim.starts_at + timedelta(hours=2)
    assert scrim.signup_open(now=late)
    signup = add_player(scrim, 0, [Role.TANK], {Role.TANK: DIAMOND_3})
    assert services.cancel(scrim=scrim, user=signup.user, now=late) is False


# --- 06-7 已结束的内战还能「取消内战」，给报名的人发「取消了」 -------------------


@pytest.mark.django_db
def test_a_finished_scrim_can_still_be_cancelled():
    scrim = make_scrim(ScrimFormat.RQ_5V5)
    Scrim.objects.filter(pk=scrim.pk).update(status=ScrimStatus.FINISHED)
    scrim.refresh_from_db()
    services.cancel_scrim(scrim=scrim)
    scrim.refresh_from_db()
    assert scrim.status == ScrimStatus.CANCELLED
    assert scrim not in services.public_scrims()


# --- 对照：6v6 / 5v5 的算法和暴力穷举一致（最优分数、并列分法的集合） -----------


def _brute(players, requirements):
    first, rest = players[0], players[1:]
    size = len(players) // 2
    best, tied = None, set()
    for others in combinations(rest, size - 1):
        team_a = (first, *others)
        team_b = tuple(p for p in rest if p not in others)
        side_a = teaming._assignments(team_a, requirements)
        side_b = teaming._assignments(team_b, requirements)
        split_best = None
        for a in side_a:
            for b in side_b:
                score = teaming._score(a, b)
                if split_best is None or score < split_best:
                    split_best = score
        if split_best is None:
            continue
        key = frozenset(p.signup_id for p in team_a)
        if best is None or split_best < best:
            best, tied = split_best, {key}
        elif split_best == best:
            tied.add(key)
    return best, tied


def _algorithm(players, requirements):
    best, tied = None, set()
    for score, a, _b in teaming._role_queue_splits(players, requirements, [None]):
        key = frozenset(i for ids in a.by_role.values() for i in ids)
        if best is None or score < best:
            best, tied = score, {key}
        elif score == best:
            tied.add(key)
    return best, tied


def _random_players(rng, count, flexible):
    players = []
    for index in range(count):
        if flexible:
            roles = ("tank", "damage", "support")
        else:
            roles = tuple(
                r for r in ("tank", "damage", "support") if rng.random() < 0.55
            ) or ("damage",)
        ratings = {r: rng.choice([0, 5, 12, 18, 22, 26, 30]) for r in roles}
        # 有时某个勾了的位置段位被改成未定级（S6 的形状）
        if len(roles) > 1 and rng.random() < 0.2:
            ratings.pop(roles[0])
        players.append(
            teaming.Player(index + 1, f"p{index}", "", roles, ratings, max(ratings.values()))
        )
    return players


@pytest.mark.parametrize(
    "fmt,count,seeds,flexible",
    [
        (ScrimFormat.RQ_5V5, 10, range(40), False),
        (ScrimFormat.RQ_5V5, 10, range(10), True),
        (ScrimFormat.RQ_6V6, 12, range(8), False),
        (ScrimFormat.RQ_6V6, 12, range(2), True),
    ],
)
def test_role_queue_matches_brute_force(fmt, count, seeds, flexible):
    requirements = ROLE_REQUIREMENTS[fmt]
    checked = 0
    for seed in seeds:
        rng = random.Random(1000 + seed)
        players = _random_players(rng, count, flexible)
        brute = _brute(players, requirements)
        if brute[0] is None:
            continue
        algo = _algorithm(players, requirements)
        assert algo == brute, (seed, algo[0], brute[0], len(algo[1]), len(brute[1]))
        checked += 1
    print(fmt, "flexible" if flexible else "mixed", "checked", checked)


def test_six_v_six_worst_case_time():
    rng = random.Random(7)
    players = [
        teaming.Player(
            i + 1,
            f"p{i}",
            "",
            ("tank", "damage", "support"),
            {r: rng.randint(0, 35) for r in ("tank", "damage", "support")},
            0,
        )
        for i in range(12)
    ]
    scrim = SimpleNamespace(
        format=ScrimFormat.RQ_6V6,
        players_needed=12,
        role_queue=True,
        get_format_display=lambda: "角色限定 6v6",
    )
    started = time.perf_counter()
    teaming.generate(players, scrim)
    elapsed = time.perf_counter() - started
    print(f"6v6 all-flex generate: {elapsed:.3f}s")
    assert elapsed < 1.0
