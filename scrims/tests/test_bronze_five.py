"""Round 068: rank score 0 is 青铜 5 (appendix A), not 「没填段位」.

Every place that read a rank used Python truthiness, so a Bronze 5 player
was refused from role-queue scrims and dropped by the split.
"""

import pytest
from django.test import RequestFactory

from scrims import services, split_admin, teaming
from scrims.models import Role, ScrimFormat
from scrims.tests.test_teaming import add_player, make_scrim

BRONZE_5 = 0


@pytest.mark.django_db
def test_a_bronze_five_rank_satisfies_the_role_queue_rule():
    scrim = make_scrim(ScrimFormat.RQ_5V5)
    signup = add_player(scrim, 1, [Role.TANK], {Role.TANK: BRONZE_5})

    assert (
        services.role_problems(scrim=scrim, account=signup.game_account, roles=["tank"])
        == []
    )


@pytest.mark.django_db
def test_a_bronze_five_rank_counts_as_a_rank_in_open_formats():
    scrim = make_scrim(ScrimFormat.OPEN_5V5)
    signup = add_player(scrim, 2, [Role.TANK], {Role.TANK: BRONZE_5})

    assert (
        services.role_problems(scrim=scrim, account=signup.game_account, roles=["tank"])
        == []
    )
    assert signup.best_rating == BRONZE_5


@pytest.mark.django_db
def test_the_signup_shows_bronze_five_not_missing():
    scrim = make_scrim(ScrimFormat.RQ_5V5)
    signup = add_player(scrim, 3, [Role.TANK], {Role.TANK: BRONZE_5})

    assert signup.rank_pairs == [("tank", "坦克 青铜 5")]


@pytest.mark.django_db
def test_the_split_keeps_a_bronze_five_rating():
    scrim = make_scrim(ScrimFormat.RQ_5V5)
    signup = add_player(scrim, 4, [Role.TANK], {Role.TANK: BRONZE_5})

    (player,) = teaming.players_from([signup], scrim)

    assert player.ratings == {"tank": BRONZE_5}


@pytest.mark.django_db
def test_the_board_keeps_a_bronze_five_rating_for_the_chosen_role():
    scrim = make_scrim(ScrimFormat.RQ_5V5)
    signup = add_player(
        scrim, 5, [Role.TANK, Role.DAMAGE], {Role.TANK: BRONZE_5, Role.DAMAGE: 22}
    )
    request = RequestFactory().post(
        "/", {f"team-{signup.pk}": "a", f"role-{signup.pk}": "tank"}
    )

    placements = split_admin._placements_from_post(request, scrim)

    # Before round 068 the 0 fell through `or best_rating` and became 22.
    assert placements[signup.pk] == ("a", "tank", BRONZE_5)
