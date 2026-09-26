"""Design 8.8.1: individual signups, the pool a tournament admin forms teams from.

Round 069. The checks mirror the ones a team member gets in 8.3, so a
person cannot sign up alone for something their captain could not have
registered them for.
"""

from datetime import timedelta

import pytest
from django.core import mail
from django.urls import reverse
from django.utils import timezone

from accounts.models import ContactMethod, Feature, FeatureUserRule, GameAccount, User
from core.models import PrerenderedPage
from teams import services as team_services
from tournaments import registration as reg
from tournaments.models import IndividualSignup, Tournament, TournamentStatus
from tournaments.tests.test_state_table import player

BRONZE_5 = 0


def _tournament(**kwargs):
    now = timezone.now()
    options = {
        "title": "新生杯",
        "registration_opens_at": now - timedelta(days=1),
        "registration_closes_at": now + timedelta(days=7),
        "roster_min": 2,
        "roster_max": 5,
        "status": TournamentStatus.PUBLISHED,
        "published_at": now,
        "allow_individual_signup": True,
    }
    options.update(kwargs)
    return Tournament.objects.create(**options)


def _sign_up(tournament, user, roles=("tank",), account=None):
    account = account or user.game_accounts.first()
    return reg.sign_up_individual(
        tournament=tournament,
        user=user,
        game_account_id=account.pk,
        roles=list(roles),
    )


@pytest.fixture
def solo(db):
    return player("solo@example.com", "散人甲")


@pytest.fixture
def prerender_on(settings, tmp_path):
    settings.PRERENDER_ENABLED = True
    settings.PRERENDER_ROOT = tmp_path


def _requested(tournament) -> bool:
    return PrerenderedPage.objects.filter(path=tournament.get_absolute_url()).exists()


# --- signing up -----------------------------------------------------------------


@pytest.mark.django_db
def test_signing_up_puts_the_player_in_the_pool(solo):
    tournament = _tournament()

    signup = _sign_up(tournament, solo, roles=("tank", "support"))

    assert signup.roles == ["tank", "support"]
    assert signup.role_labels == ["坦克", "支援"]
    assert not signup.is_placed
    assert list(reg.individual_pool(tournament)) == [signup]


@pytest.mark.django_db
def test_signing_up_again_updates_the_entry(solo):
    tournament = _tournament()
    GameAccount.objects.create(user=solo, battletag="Second#2222", rank_tank=20)
    first = _sign_up(tournament, solo, roles=("tank",))
    other = solo.game_accounts.get(battletag="Second#2222")

    again = reg.sign_up_individual(
        tournament=tournament, user=solo, game_account_id=other.pk, roles=["damage"]
    )

    assert again.pk == first.pk
    assert tournament.individual_signups.count() == 1
    assert again.game_account == other
    assert again.roles == ["damage"]


@pytest.mark.django_db
def test_the_pool_counts_each_role(solo):
    tournament = _tournament()
    _sign_up(tournament, solo, roles=("tank", "damage"))
    _sign_up(tournament, player("solo2@example.com", "散人乙"), roles=("damage",))

    assert reg.pool_counts(reg.individual_pool(tournament)) == {
        "total": 2,
        "tank": 1,
        "damage": 2,
        "support": 0,
    }


# --- every refusal --------------------------------------------------------------


@pytest.mark.django_db
def test_the_switch_must_be_on(solo):
    tournament = _tournament(allow_individual_signup=False)
    with pytest.raises(reg.RegistrationError, match="不接受个人报名"):
        _sign_up(tournament, solo)


@pytest.mark.django_db
def test_the_window_must_be_open(solo):
    now = timezone.now()
    tournament = _tournament(
        registration_opens_at=now - timedelta(days=9),
        registration_closes_at=now - timedelta(days=1),
    )
    with pytest.raises(reg.RegistrationError, match="不在报名时间内"):
        _sign_up(tournament, solo)


@pytest.mark.django_db
def test_a_draft_tournament_is_closed(solo):
    tournament = _tournament(status=TournamentStatus.DRAFT, published_at=None)
    with pytest.raises(reg.RegistrationError, match="不在报名时间内"):
        _sign_up(tournament, solo)


@pytest.mark.django_db
def test_the_feature_rule_applies(solo):
    tournament = _tournament()
    FeatureUserRule.objects.create(
        user=solo, feature=Feature.TOURNAMENT_REGISTER, allowed=False
    )
    with pytest.raises(reg.RegistrationError, match="暂时无法参加赛事报名"):
        _sign_up(tournament, solo)


@pytest.mark.django_db
def test_the_profile_must_be_complete(solo):
    tournament = _tournament()
    ContactMethod.objects.filter(user=solo).delete()
    with pytest.raises(reg.RegistrationError, match="资料不完整"):
        _sign_up(tournament, solo)


@pytest.mark.django_db
def test_sjtu_only_applies(solo):
    tournament = _tournament(sjtu_only=True)
    User.objects.filter(pk=solo.pk).update(is_sjtu=False)
    solo.refresh_from_db()
    with pytest.raises(reg.RegistrationError, match="仅限交大"):
        _sign_up(tournament, solo)


@pytest.mark.django_db
def test_someone_on_a_team_roster_cannot_also_sign_up_alone(solo):
    """Design 8.3 check 8 holds for the pool too."""
    tournament = _tournament()
    mate = player("solo-mate@example.com", "队友")
    team = team_services.create_team(user=solo, name="散人的战队")
    application = team_services.apply_to_team(
        team=team, user=mate, roles={"tank": True}
    )
    team_services.approve_application(application=application, actor=solo)
    selections = {
        str(m.user.pk): m.user.game_accounts.first().pk for m in team.memberships.all()
    }
    reg.submit(tournament=tournament, team=team, actor=solo, selections=selections)

    with pytest.raises(reg.RegistrationError, match="名单中"):
        _sign_up(tournament, mate)


@pytest.mark.django_db
def test_the_game_id_must_be_your_own(solo):
    tournament = _tournament()
    stranger = player("stranger@example.com", "路人")
    with pytest.raises(reg.RegistrationError, match="自己的游戏 ID"):
        _sign_up(tournament, solo, account=stranger.game_accounts.first())


@pytest.mark.django_db
def test_at_least_one_role(solo):
    tournament = _tournament()
    with pytest.raises(reg.RegistrationError, match="至少要勾选一个"):
        _sign_up(tournament, solo, roles=())


@pytest.mark.django_db
def test_a_placed_player_cannot_change_or_cancel(solo):
    """Design 8.8.1: once on a team, changes go through the team (8.8.2)."""
    tournament = _tournament()
    signup = _sign_up(tournament, solo)
    from tournaments.models import Registration

    holder = Registration.objects.create(
        tournament=tournament,
        team=team_services.create_team(
            user=player("holder@example.com", "占位队长"), name="临时占位"
        ),
        team_name="临时占位",
        submitted_by=solo,
    )
    IndividualSignup.objects.filter(pk=signup.pk).update(registration=holder)

    with pytest.raises(reg.RegistrationError, match="已经被编入队伍"):
        _sign_up(tournament, solo, roles=("damage",))
    with pytest.raises(reg.RegistrationError, match="已经被编入队伍"):
        reg.cancel_individual(tournament=tournament, user=solo)


# --- cancelling -----------------------------------------------------------------


@pytest.mark.django_db
def test_cancelling_before_the_deadline_leaves_the_pool(solo):
    tournament = _tournament()
    _sign_up(tournament, solo)

    reg.cancel_individual(tournament=tournament, user=solo)

    assert not tournament.individual_signups.exists()


@pytest.mark.django_db
def test_cancelling_after_the_deadline_is_refused(solo):
    tournament = _tournament()
    _sign_up(tournament, solo)
    Tournament.objects.filter(pk=tournament.pk).update(
        registration_closes_at=timezone.now() - timedelta(hours=1)
    )
    tournament.refresh_from_db()

    with pytest.raises(reg.RegistrationError, match="报名已截止"):
        reg.cancel_individual(tournament=tournament, user=solo)
    assert tournament.individual_signups.exists()


@pytest.mark.django_db
def test_cancelling_without_a_signup_is_refused(solo):
    tournament = _tournament()
    with pytest.raises(reg.RegistrationError, match="还没有个人报名"):
        reg.cancel_individual(tournament=tournament, user=solo)


# --- the public page ------------------------------------------------------------


@pytest.mark.django_db
def test_the_page_lists_nicknames_and_roles_only(client, solo):
    tournament = _tournament()
    account = solo.game_accounts.first()
    account.rank_tank = BRONZE_5
    account.save()
    _sign_up(tournament, solo, roles=("tank", "support"))

    html = client.get(tournament.get_absolute_url()).content.decode()

    assert "个人报名" in html
    assert solo.nickname in html
    assert "坦克" in html and "支援" in html
    assert account.battletag not in html
    assert "青铜" not in html
    assert "共 1 人：坦克 1、输出 0、支援 1" in html


@pytest.mark.django_db
def test_the_page_hides_the_pool_when_the_switch_is_off(client, solo):
    tournament = _tournament(allow_individual_signup=False)

    html = client.get(tournament.get_absolute_url()).content.decode()

    assert "还没有人个人报名" not in html
    assert "需要由队长为战队报名" not in html  # anonymous: login prompt only


@pytest.mark.django_db
def test_the_static_page_has_no_form_and_no_logout_marker(prerender_on, solo):
    """Design 13.13.5: prerendered pages carry nothing personal."""
    from core import prerender

    tournament = _tournament()
    _sign_up(tournament, solo)

    record = prerender.generate(tournament.get_absolute_url())

    assert record.status == PrerenderedPage.Status.READY
    html = open_static(tournament)
    assert "csrfmiddlewaretoken" not in html
    assert "退出" not in html
    assert solo.nickname in html


def open_static(tournament):
    from django.conf import settings

    path = settings.PRERENDER_ROOT / "tournaments" / str(tournament.pk) / "index.html"
    return path.read_text(encoding="utf-8")


# --- the slot -------------------------------------------------------------------


def _slot(client, tournament):
    url = reverse("state_fragment") + f"?slots=tournament-actions:{tournament.pk}"
    return client.get(url).content.decode()


@pytest.mark.django_db
def test_a_player_without_a_team_sees_the_individual_entry(client, solo):
    tournament = _tournament()
    client.force_login(solo)

    fragment = _slot(client, tournament)
    page = client.get(tournament.get_absolute_url()).content.decode()

    for html in (fragment, page):
        assert reverse("tournament_individual_signup", args=[tournament.pk]) in html
        assert "需要由队长为战队报名" not in html


@pytest.mark.django_db
def test_the_entry_shows_the_signup_and_the_cancel_button(client, solo):
    tournament = _tournament()
    _sign_up(tournament, solo, roles=("damage",))
    client.force_login(solo)

    fragment = _slot(client, tournament)

    assert "等待编队" in fragment
    assert "输出" in fragment
    assert reverse("tournament_individual_cancel", args=[tournament.pk]) in fragment


@pytest.mark.django_db
def test_the_entry_lists_problems_instead_of_the_button(client, solo):
    tournament = _tournament()
    ContactMethod.objects.filter(user=solo).delete()
    client.force_login(solo)

    fragment = _slot(client, tournament)

    assert "暂时不能个人报名" in fragment
    assert "资料不完整" in fragment
    assert reverse("tournament_individual_signup", args=[tournament.pk]) not in fragment


@pytest.mark.django_db
def test_without_the_switch_the_old_prompt_stays(client, solo):
    tournament = _tournament(allow_individual_signup=False)
    client.force_login(solo)

    assert "需要由队长为战队报名" in _slot(client, tournament)


@pytest.mark.django_db
def test_a_captain_keeps_the_team_entry(client, solo):
    tournament = _tournament()
    team_services.create_team(user=solo, name="散人的战队")
    client.force_login(solo)

    fragment = _slot(client, tournament)

    assert reverse("tournament_register", args=[tournament.pk]) in fragment
    assert reverse("tournament_individual_signup", args=[tournament.pk]) not in fragment


# --- the pages --------------------------------------------------------------------


@pytest.mark.django_db
def test_the_signup_page_round_trip(client, solo):
    tournament = _tournament()
    client.force_login(solo)
    url = reverse("tournament_individual_signup", args=[tournament.pk])

    assert client.get(url).status_code == 200
    response = client.post(
        url,
        {"game_account": solo.game_accounts.first().pk, "roles": ["tank", "damage"]},
    )

    assert response.status_code == 302
    assert response.url == tournament.get_absolute_url()
    assert tournament.individual_signups.get(user=solo).roles == ["tank", "damage"]

    cancel = client.post(reverse("tournament_individual_cancel", args=[tournament.pk]))
    assert cancel.status_code == 302
    assert not tournament.individual_signups.exists()


@pytest.mark.django_db
def test_the_signup_page_shows_the_problems(client, solo):
    tournament = _tournament()
    client.force_login(solo)
    url = reverse("tournament_individual_signup", args=[tournament.pk])

    response = client.post(url, {"game_account": solo.game_accounts.first().pk})

    assert response.status_code == 200
    assert "至少要勾选一个" in response.content.decode()
    assert not tournament.individual_signups.exists()


@pytest.mark.django_db
def test_the_signup_page_needs_login_and_a_public_tournament(client, solo):
    tournament = _tournament()
    url = reverse("tournament_individual_signup", args=[tournament.pk])
    assert client.get(url).status_code == 302

    draft = _tournament(status=TournamentStatus.DRAFT, published_at=None)
    client.force_login(solo)
    assert (
        client.get(reverse("tournament_individual_signup", args=[draft.pk])).status_code
        == 404
    )


@pytest.mark.django_db
def test_my_registrations_lists_the_pool_entry(client, solo):
    tournament = _tournament()
    _sign_up(tournament, solo, roles=("support",))
    client.force_login(solo)

    html = client.get(reverse("me_registrations")).content.decode()

    assert tournament.title in html
    assert "等待编队" in html
    assert reverse("tournament_individual_cancel", args=[tournament.pk]) in html


# --- regeneration (design 13.13.4) -------------------------------------------------


@pytest.mark.django_db
def test_signing_up_and_cancelling_refresh_the_page(prerender_on, solo):
    tournament = _tournament()

    _sign_up(tournament, solo)
    assert _requested(tournament)

    PrerenderedPage.objects.all().delete()
    reg.cancel_individual(tournament=tournament, user=solo)
    assert _requested(tournament)


@pytest.mark.django_db
def test_an_unlisted_tournament_is_not_regenerated(prerender_on, solo):
    tournament = _tournament(status=TournamentStatus.CANCELLED)
    Tournament.objects.filter(pk=tournament.pk).update(
        status=TournamentStatus.PUBLISHED
    )
    tournament.refresh_from_db()
    _sign_up(tournament, solo)
    PrerenderedPage.objects.all().delete()
    Tournament.objects.filter(pk=tournament.pk).update(
        status=TournamentStatus.CANCELLED
    )
    tournament.refresh_from_db()

    reg._refresh_tournament_page(tournament)

    assert not _requested(tournament)


@pytest.mark.django_db
def test_a_nickname_change_refreshes_the_pool_page(prerender_on, solo):
    from accounts.services import refresh_nickname_pages

    tournament = _tournament()
    _sign_up(tournament, solo)
    PrerenderedPage.objects.all().delete()

    refresh_nickname_pages(solo)

    assert _requested(tournament)


# --- the account side (design 3.5.2, 3.8) --------------------------------------------


@pytest.mark.django_db
def test_a_pooled_game_id_cannot_be_deleted(client, solo):
    from accounts.services import deletion_blocked_reason

    tournament = _tournament()
    account = solo.game_accounts.first()
    assert deletion_blocked_reason(account) is None
    _sign_up(tournament, solo)

    reason = deletion_blocked_reason(account)
    assert reason and "个人报名" in reason and tournament.title in reason

    client.force_login(solo)
    response = client.post(
        reverse("me_game_account_delete", args=[account.pk]), HTTP_HX_REQUEST="true"
    )
    assert response.status_code == 400
    assert solo.game_accounts.filter(pk=account.pk).exists()


@pytest.mark.django_db
def test_a_finished_tournament_lets_the_game_id_go(solo):
    from accounts.services import deletion_blocked_reason

    tournament = _tournament()
    _sign_up(tournament, solo)
    Tournament.objects.filter(pk=tournament.pk).update(status=TournamentStatus.FINISHED)

    assert deletion_blocked_reason(solo.game_accounts.first()) is None


@pytest.mark.django_db
def test_deleting_the_account_clears_the_pool_entries(solo):
    from accounts.services import delete_account

    tournament = _tournament()
    _sign_up(tournament, solo)

    delete_account(solo)

    assert not tournament.individual_signups.exists()


@pytest.mark.django_db
def test_the_export_lists_the_pool_entry(solo):
    from accounts.services import personal_data

    tournament = _tournament()
    _sign_up(tournament, solo, roles=("tank",))

    data = personal_data(solo)

    assert data["individual_signups"] == [
        {
            "tournament": tournament.title,
            "battletag": solo.game_accounts.first().battletag,
            "roles": ["坦克"],
            "created_at": data["individual_signups"][0]["created_at"],
            "team": None,
        }
    ]


# --- the admin form ----------------------------------------------------------------


@pytest.mark.django_db
def test_the_admin_form_has_the_switch():
    from tournaments.wagtail_hooks import TournamentViewSet

    form_class = TournamentViewSet().get_form_class(for_update=True)

    assert "allow_individual_signup" in form_class.base_fields


@pytest.mark.django_db
def test_nothing_here_sends_mail(solo, django_capture_on_commit_callbacks):
    tournament = _tournament()
    mail.outbox.clear()
    with django_capture_on_commit_callbacks(execute=True):
        _sign_up(tournament, solo)
        reg.cancel_individual(tournament=tournament, user=solo)
    assert mail.outbox == []
