from datetime import timedelta

import pytest
from django.core import mail
from django.urls import reverse
from django.utils import timezone

from accounts.models import (
    ContactMethod,
    ContactType,
    Feature,
    FeatureUserRule,
    GameAccount,
    User,
)
from teams import services as team_services
from tournaments import registration as reg
from tournaments.models import (
    ActorType,
    Registration,
    RegistrationMember,
    RegistrationStatus,
    ReviewMode,
    Tournament,
    TournamentStatus,
)


def _player(email, nickname, *, sjtu=True, battletag=None):
    user = User.objects.create_user(
        email=email,
        password="Correct-Horse-Battery-1",
        nickname=nickname,
        is_sjtu=sjtu,
        agreed_terms_at=timezone.now(),
        agreed_cross_border_at=timezone.now(),
    )
    GameAccount.objects.create(user=user, battletag=battletag or f"{nickname}#1234")
    ContactMethod.objects.create(user=user, type=ContactType.QQ, value="123456789")
    return user


def _tournament(**kwargs):
    now = timezone.now()
    kwargs.setdefault("title", "春季赛")
    kwargs.setdefault("registration_opens_at", now - timedelta(days=1))
    kwargs.setdefault("registration_closes_at", now + timedelta(days=7))
    kwargs.setdefault("roster_min", 2)
    kwargs.setdefault("roster_max", 3)
    kwargs.setdefault("status", TournamentStatus.PUBLISHED)
    kwargs.setdefault("published_at", now)
    return Tournament.objects.create(**kwargs)


@pytest.fixture
def captain(db):
    return _player("cap-reg@example.com", "队长报名")


@pytest.fixture
def mate(db):
    return _player("mate-reg@example.com", "队员报名")


@pytest.fixture
def team(captain, mate):
    team = team_services.create_team(user=captain, name="报名战队")
    application = team_services.apply_to_team(
        team=team, user=mate, roles={"tank": True}
    )
    team_services.approve_application(application=application, actor=captain)
    return team


def _selections(team):
    return {
        str(membership.user.pk): membership.user.game_accounts.first().pk
        for membership in team.memberships.all()
    }


# --- the eight checks ----------------------------------------------------------


@pytest.mark.django_db
def test_submit_writes_registration_roster_and_log(team, captain):
    tournament = _tournament()
    registration = reg.submit(
        tournament=tournament,
        team=team,
        actor=captain,
        selections=_selections(team),
    )
    assert registration.status == RegistrationStatus.PENDING
    assert registration.roster_version == 1
    assert registration.team_name == team.name
    assert registration.members.count() == 2
    assert registration.logs.count() == 1
    log = registration.logs.first()
    assert log.action == "submit"
    assert log.roster_snapshot and len(log.roster_snapshot) == 2


@pytest.mark.django_db
def test_check_1_outside_the_window(team, captain):
    now = timezone.now()
    tournament = _tournament(
        registration_opens_at=now - timedelta(days=5),
        registration_closes_at=now - timedelta(days=1),
    )
    with pytest.raises(reg.RegistrationError) as exc:
        reg.submit(
            tournament=tournament,
            team=team,
            actor=captain,
            selections=_selections(team),
        )
    assert "不在报名时间内" in str(exc.value)


@pytest.mark.django_db
def test_check_2_only_the_captain(team, mate):
    tournament = _tournament()
    with pytest.raises(reg.RegistrationError) as exc:
        reg.submit(
            tournament=tournament,
            team=team,
            actor=mate,
            selections=_selections(team),
        )
    assert "只有队长" in str(exc.value)


@pytest.mark.django_db
def test_check_3_roster_size(team, captain):
    tournament = _tournament(roster_min=3, roster_max=5)
    with pytest.raises(reg.RegistrationError) as exc:
        reg.submit(
            tournament=tournament,
            team=team,
            actor=captain,
            selections=_selections(team),
        )
    assert "要求 3 到 5 人" in str(exc.value)


@pytest.mark.django_db
def test_check_4_incomplete_profile(team, captain, mate):
    ContactMethod.objects.filter(user=mate).delete()
    tournament = _tournament()
    with pytest.raises(reg.RegistrationError) as exc:
        reg.submit(
            tournament=tournament,
            team=team,
            actor=captain,
            selections=_selections(team),
        )
    assert "资料不完整" in str(exc.value)


@pytest.mark.django_db
def test_check_5_blocked_or_inactive_member(team, captain, mate):
    FeatureUserRule.objects.create(
        user=mate, feature=Feature.TOURNAMENT_REGISTER, allowed=False
    )
    tournament = _tournament()
    with pytest.raises(reg.RegistrationError) as exc:
        reg.submit(
            tournament=tournament,
            team=team,
            actor=captain,
            selections=_selections(team),
        )
    assert "暂时无法参加赛事报名" in str(exc.value)


@pytest.mark.django_db
def test_check_6_sjtu_only(team, captain, mate):
    mate.is_sjtu = False
    mate.save()
    tournament = _tournament(sjtu_only=True)
    with pytest.raises(reg.RegistrationError) as exc:
        reg.submit(
            tournament=tournament,
            team=team,
            actor=captain,
            selections=_selections(team),
        )
    assert "仅限交大" in str(exc.value)


@pytest.mark.django_db
def test_check_7_game_id_must_belong_to_the_member(team, captain, mate):
    tournament = _tournament()
    stranger = _player("stranger-reg@example.com", "外人")
    selections = _selections(team)
    selections[str(mate.pk)] = stranger.game_accounts.first().pk
    with pytest.raises(reg.RegistrationError) as exc:
        reg.submit(
            tournament=tournament, team=team, actor=captain, selections=selections
        )
    assert "游戏 ID 选择有误" in str(exc.value)


@pytest.mark.django_db
def test_check_8_member_already_on_another_roster(team, captain, mate):
    tournament = _tournament()
    reg.submit(
        tournament=tournament, team=team, actor=captain, selections=_selections(team)
    )
    other_captain = _player("other-cap@example.com", "另一个队长")
    other_team = team_services.create_team(user=other_captain, name="另一支战队")
    application = team_services.apply_to_team(
        team=other_team, user=mate, roles={"tank": True}
    )
    team_services.approve_application(application=application, actor=other_captain)
    with pytest.raises(reg.RegistrationError) as exc:
        reg.submit(
            tournament=tournament,
            team=other_team,
            actor=other_captain,
            selections=_selections(other_team),
        )
    assert "已经在该赛事的战队「报名战队」名单中" in str(exc.value)


@pytest.mark.django_db
def test_all_problems_are_listed_at_once(team, captain, mate):
    ContactMethod.objects.filter(user=mate).delete()
    mate.is_sjtu = False
    mate.save()
    tournament = _tournament(sjtu_only=True, roster_min=3, roster_max=4)
    with pytest.raises(reg.RegistrationError) as exc:
        reg.submit(
            tournament=tournament,
            team=team,
            actor=captain,
            selections=_selections(team),
        )
    assert len(exc.value.problems) >= 3


@pytest.mark.django_db(transaction=True)
def test_database_backs_up_check_8(team, captain, mate):
    from django.db.utils import IntegrityError

    tournament = _tournament()
    registration = reg.submit(
        tournament=tournament, team=team, actor=captain, selections=_selections(team)
    )
    other_captain = _player("dup-cap@example.com", "重复队长")
    other_team = team_services.create_team(user=other_captain, name="重复战队")
    other = Registration.objects.create(
        tournament=tournament, team=other_team, team_name=other_team.name
    )
    with pytest.raises(IntegrityError):
        RegistrationMember.objects.create(
            registration=other,
            tournament=tournament,
            user=mate,  # already active on the first roster
            nickname=mate.nickname,
            battletag="X#1",
            is_active=True,
        )
    assert registration.members.filter(user=mate).exists()


# --- roster lock and sync ------------------------------------------------------


@pytest.mark.django_db
def test_roster_is_frozen(team, captain, mate):
    tournament = _tournament()
    registration = reg.submit(
        tournament=tournament, team=team, actor=captain, selections=_selections(team)
    )
    mate.nickname = "改了名字"
    mate.save()
    GameAccount.objects.filter(user=mate).update(rank_tank=40)
    member = registration.members.get(user=mate)
    assert member.nickname == "队员报名"
    assert member.rank_tank is None


@pytest.mark.django_db
def test_sync_bumps_the_version_and_resets_the_status(team, captain):
    tournament = _tournament()
    registration = reg.submit(
        tournament=tournament, team=team, actor=captain, selections=_selections(team)
    )
    reg.approve(registration=registration, actor=captain)
    registration.refresh_from_db()
    assert registration.status == RegistrationStatus.APPROVED

    third = _player("third@example.com", "第三人")
    application = team_services.apply_to_team(
        team=team, user=third, roles={"damage": True}
    )
    team_services.approve_application(application=application, actor=captain)
    assert reg.roster_differs_from_team(registration) is True

    synced = reg.submit(
        tournament=tournament, team=team, actor=captain, selections=_selections(team)
    )
    assert synced.pk == registration.pk
    assert synced.roster_version == 2
    assert synced.status == RegistrationStatus.PENDING
    assert synced.members.count() == 3
    assert synced.logs.filter(action="sync_roster").exists()


# --- the state machine ---------------------------------------------------------


@pytest.mark.django_db
def test_local_review_flow(team, captain):
    tournament = _tournament(review_mode=ReviewMode.LOCAL)
    registration = reg.submit(
        tournament=tournament, team=team, actor=captain, selections=_selections(team)
    )
    reg.approve(registration=registration, actor=captain)
    registration.refresh_from_db()
    assert registration.status == RegistrationStatus.APPROVED

    reg.reject(registration=registration, actor=captain, note="名单不符合要求")
    registration.refresh_from_db()
    assert registration.status == RegistrationStatus.REJECTED
    assert registration.status_note == "名单不符合要求"
    assert registration.logs.filter(action="revoke").exists()


@pytest.mark.django_db
def test_two_stage_review_waits_for_upstream(team, captain):
    tournament = _tournament(review_mode=ReviewMode.TWO_STAGE)
    registration = reg.submit(
        tournament=tournament, team=team, actor=captain, selections=_selections(team)
    )
    reg.approve(registration=registration, actor=captain)
    registration.refresh_from_db()
    assert registration.status == RegistrationStatus.AWAITING_UPSTREAM

    with pytest.raises(reg.RegistrationError):
        reg.approve(registration=registration, actor=captain)

    reg.approve(registration=registration, actor=None, actor_type=ActorType.UPSTREAM)
    registration.refresh_from_db()
    assert registration.status == RegistrationStatus.APPROVED


@pytest.mark.django_db
def test_upstream_mode_locks_out_local_admins(team, captain):
    tournament = _tournament(review_mode=ReviewMode.UPSTREAM)
    registration = reg.submit(
        tournament=tournament, team=team, actor=captain, selections=_selections(team)
    )
    with pytest.raises(reg.RegistrationError) as exc:
        reg.approve(registration=registration, actor=captain)
    assert "上游审核" in str(exc.value)

    reg.approve(registration=registration, actor=None, actor_type=ActorType.UPSTREAM)
    registration.refresh_from_db()
    assert registration.status == RegistrationStatus.APPROVED


@pytest.mark.django_db
def test_rejection_requires_a_note(team, captain):
    tournament = _tournament()
    registration = reg.submit(
        tournament=tournament, team=team, actor=captain, selections=_selections(team)
    )
    with pytest.raises(reg.RegistrationError) as exc:
        reg.reject(registration=registration, actor=captain, note="  ")
    assert "备注" in str(exc.value)


@pytest.mark.django_db
def test_withdraw_and_resubmit(team, captain):
    tournament = _tournament()
    registration = reg.submit(
        tournament=tournament, team=team, actor=captain, selections=_selections(team)
    )
    reg.withdraw(registration=registration, actor=captain)
    registration.refresh_from_db()
    assert registration.status == RegistrationStatus.WITHDRAWN
    assert registration.members.filter(is_active=True).count() == 0

    again = reg.submit(
        tournament=tournament, team=team, actor=captain, selections=_selections(team)
    )
    assert again.status == RegistrationStatus.PENDING
    assert again.roster_version == 2
    assert again.logs.filter(action="resubmit").exists()


@pytest.mark.django_db
def test_withdrawn_roster_frees_the_players(team, captain, mate):
    tournament = _tournament()
    registration = reg.submit(
        tournament=tournament, team=team, actor=captain, selections=_selections(team)
    )
    reg.withdraw(registration=registration, actor=captain)

    other_captain = _player("free-cap@example.com", "接收队长")
    other_team = team_services.create_team(user=other_captain, name="接收战队")
    application = team_services.apply_to_team(
        team=other_team, user=mate, roles={"tank": True}
    )
    team_services.approve_application(application=application, actor=other_captain)
    second = reg.submit(
        tournament=tournament,
        team=other_team,
        actor=other_captain,
        selections=_selections(other_team),
    )
    assert second.status == RegistrationStatus.PENDING


@pytest.mark.django_db
def test_captain_cannot_act_after_the_deadline(team, captain):
    tournament = _tournament()
    registration = reg.submit(
        tournament=tournament, team=team, actor=captain, selections=_selections(team)
    )
    Tournament.objects.filter(pk=tournament.pk).update(
        registration_closes_at=timezone.now() - timedelta(minutes=1)
    )
    registration.refresh_from_db()
    with pytest.raises(reg.RegistrationError) as exc:
        reg.withdraw(registration=registration, actor=captain)
    assert "已截止" in str(exc.value)


# --- mails ---------------------------------------------------------------------


@pytest.mark.django_db
def test_mails(team, captain, django_capture_on_commit_callbacks):
    tournament = _tournament()
    mail.outbox.clear()
    with django_capture_on_commit_callbacks(execute=True):
        registration = reg.submit(
            tournament=tournament,
            team=team,
            actor=captain,
            selections=_selections(team),
        )
    assert len(mail.outbox) == 1
    assert captain.email in mail.outbox[0].recipients()
    assert "报名已提交" in mail.outbox[0].subject

    mail.outbox.clear()
    with django_capture_on_commit_callbacks(execute=True):
        reg.reject(registration=registration, actor=captain, note="名单人数不足")
    assert len(mail.outbox) == 1
    assert "名单人数不足" in mail.outbox[0].body


# --- pages ---------------------------------------------------------------------


@pytest.mark.django_db
def test_registration_pages(client, team, captain, mate):
    tournament = _tournament()
    client.force_login(captain)
    page = client.get(reverse("tournament_register", args=[tournament.pk]))
    assert page.status_code == 200
    assert "队员报名" in page.content.decode()

    response = client.post(
        reverse("tournament_register", args=[tournament.pk]),
        {
            "action": "submit",
            "team": team.pk,
            **{
                f"account-{user_pk}": account_pk
                for user_pk, account_pk in _selections(team).items()
            },
        },
        follow=True,
    )
    assert response.status_code == 200
    registration = Registration.objects.get()
    assert registration.status == RegistrationStatus.PENDING

    detail = client.get(registration.get_absolute_url())
    assert detail.status_code == 200
    assert "名单快照" in detail.content.decode()

    # A roster member may look, a stranger may not.
    client.force_login(mate)
    assert client.get(registration.get_absolute_url()).status_code == 200
    stranger = _player("nosee@example.com", "看不到")
    client.force_login(stranger)
    assert client.get(registration.get_absolute_url()).status_code == 404


@pytest.mark.django_db
def test_me_registrations_lists_for_members(client, team, captain, mate):
    tournament = _tournament()
    reg.submit(
        tournament=tournament, team=team, actor=captain, selections=_selections(team)
    )
    client.force_login(mate)
    html = client.get(reverse("me_registrations")).content.decode()
    assert tournament.title in html
    assert "报名战队" in html


@pytest.mark.django_db
def test_approved_team_shows_on_the_tournament_page(client, team, captain):
    from tournaments import services

    tournament = _tournament()
    registration = reg.submit(
        tournament=tournament, team=team, actor=captain, selections=_selections(team)
    )
    assert services.approved_teams(tournament) == []
    reg.approve(registration=registration, actor=captain)
    entries = services.approved_teams(tournament)
    assert entries[0]["team_name"] == "报名战队"
    assert entries[0]["member_count"] == 2
    html = client.get(tournament.get_absolute_url()).content.decode()
    assert "报名战队" in html


@pytest.mark.django_db
def test_cancelling_a_tournament_mails_the_captains(
    team, captain, django_capture_on_commit_callbacks
):
    from tournaments import services

    tournament = _tournament()
    reg.submit(
        tournament=tournament, team=team, actor=captain, selections=_selections(team)
    )
    assert services.has_registrations(tournament) is True
    mail.outbox.clear()
    with django_capture_on_commit_callbacks(execute=True):
        services.cancel(tournament=tournament, actor=captain, reason="场地问题")
    assert any("赛事已取消" in message.subject for message in mail.outbox)


@pytest.mark.django_db
def test_live_page_shows_the_same_entry_as_the_fragment(client, team, captain):
    tournament = _tournament()
    client.force_login(captain)
    page = client.get(tournament.get_absolute_url()).content.decode()
    fragment = client.get(
        reverse("state_fragment") + f"?slots=tournament-actions:{tournament.pk}"
    ).content.decode()
    assert "为战队报名" in page
    assert "为战队报名" in fragment

    registration = reg.submit(
        tournament=tournament, team=team, actor=captain, selections=_selections(team)
    )
    page = client.get(tournament.get_absolute_url()).content.decode()
    assert "查看报名" in page
    assert registration.get_absolute_url() in page
