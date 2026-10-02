"""What the public pages show about a person (docs/design-details.md 2.2,
3; v5.2): motto, positions, the best rank per position and its switch."""

from datetime import timedelta

import pytest
from django.utils import timezone

from accounts.forms import ProfileForm
from accounts.models import GameAccount
from accounts.ranks import encode_rank
from accounts.roles import best_ranks, join_roles, parse_roles, public_profile
from core.templatetags.ow import hue, initial
from scrims.tests.test_scrims import make_user

DIAMOND_3 = encode_rank("diamond", 3)
MASTER_1 = encode_rank("master", 1)
GOLD_2 = encode_rank("gold", 2)


def test_roles_keep_one_fixed_order_and_drop_unknown_codes():
    assert parse_roles("support,tank,tank,healer") == ["tank", "support"]
    assert parse_roles(["damage", "tank"]) == ["tank", "damage"]
    assert join_roles(["support", "tank"]) == "tank,support"
    assert parse_roles("") == []


@pytest.mark.django_db
def test_each_position_shows_its_best_rank_over_every_game_id():
    """3.3 #1: a second, lower account does not pull the rank down."""
    user = make_user("p@example.com", "排位", tank=GOLD_2, damage=DIAMOND_3)
    GameAccount.objects.create(
        user=user, battletag="小号#5678", rank_tank=MASTER_1, rank_damage=GOLD_2
    )
    best = best_ranks(user.game_accounts.all())
    assert best["tank"].score == MASTER_1
    assert best["damage"].score == DIAMOND_3
    assert "support" not in best


@pytest.mark.django_db
def test_a_rank_older_than_180_days_is_marked_stale():
    user = make_user("s@example.com", "老段位", damage=DIAMOND_3)
    now = timezone.now()
    GameAccount.objects.filter(user=user).update(
        ranks_updated_at=now - timedelta(days=181)
    )
    assert best_ranks(user.game_accounts.all(), now=now)["damage"].stale
    GameAccount.objects.filter(user=user).update(
        ranks_updated_at=now - timedelta(days=179)
    )
    assert not best_ranks(user.game_accounts.all(), now=now)["damage"].stale


@pytest.mark.django_db
def test_positions_put_the_main_first_and_choose_which_ranks_show():
    user = make_user(
        "r@example.com", "位置", tank=GOLD_2, damage=DIAMOND_3, support=MASTER_1
    )
    # Nothing chosen: every ranked position, highest first (3.3 #2).
    profile = public_profile(user)
    assert profile.roles == []
    assert [rank.role for rank in profile.ranks] == ["support", "damage", "tank"]
    # Main 输出, also 坦克: those two, the main first (3.2, 3.3 #3).
    user.main_role, user.flex_roles = "damage", "tank,damage"
    profile = public_profile(user)
    assert profile.roles == ["damage", "tank"]
    assert profile.main_rank.role == "damage"
    assert [rank.role for rank in profile.ranks] == ["damage", "tank"]
    assert profile.role_items[0] == ("damage", "输出", True)
    assert not profile.is_flex
    user.flex_roles = "tank,support"
    assert public_profile(user).is_flex


@pytest.mark.django_db
def test_turning_the_switch_off_hides_every_rank_but_not_the_positions():
    user = make_user("h@example.com", "不公开", damage=DIAMOND_3)
    user.main_role, user.show_rank = "damage", False
    profile = public_profile(user)
    assert profile.roles == ["damage"]
    assert profile.ranks == [] and profile.main_rank is None


@pytest.mark.django_db
def test_the_profile_form_keeps_the_motto_on_one_line_without_links():
    user = make_user("f@example.com", "表单")

    def form(**data):
        base = {"nickname": "表单", "is_sjtu": "true", "show_rank": "on"}
        return ProfileForm({**base, **data}, instance=user)

    ok = form(motto="  推车不停，\n开团   不怂  ")
    assert ok.is_valid(), ok.errors
    assert ok.cleaned_data["motto"] == "推车不停， 开团 不怂"
    for link in ("看这里 https://x.cn", "www.example.com", "加群 abc.com"):
        bad = form(motto=link)
        assert not bad.is_valid()
        assert "不能放链接" in bad.errors["motto"][0]
    long = form(motto="字" * 31)
    assert not long.is_valid()


@pytest.mark.django_db
def test_the_main_position_is_not_repeated_as_a_flex_one():
    user = make_user("m@example.com", "主位")
    form = ProfileForm(
        {
            "nickname": "主位",
            "is_sjtu": "true",
            "main_role": "support",
            "flex_roles": ["support", "tank"],
        },
        instance=user,
    )
    assert form.is_valid(), form.errors
    saved = form.save()
    assert saved.main_role == "support"
    assert saved.flex_roles == "tank"
    assert saved.show_rank is False  # an unticked box


def test_initials_skip_symbols_and_take_a_letter_or_a_character():
    """design-details 2.2."""
    assert initial("林间小鹿") == "林"
    assert initial("  ☆mercy") == "M"
    assert initial("🔥 火") == "火"
    assert initial("!!!") == "?"
    assert initial("") == "?"


def test_people_and_teams_keep_one_of_five_pictures_by_id():
    class Thing:
        def __init__(self, pk):
            self.pk = pk

    assert [hue(Thing(pk)) for pk in range(1, 7)] == [2, 3, 4, 5, 1, 2]
    assert hue(None) == 1
