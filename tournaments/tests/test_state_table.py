"""Design 8.5's state transition table, walked row by row.

Round 015 covered the eight submission checks and the common flows; round
018 found three holes in this table that the existing tests did not reach
(an upstream acting in local mode, an upstream skipping the local stage in
two-stage mode, review not being idempotent). Those were found by reading
the table, not by running the suite.

So this file is the table itself: every row, every mode, both the actor
who may and an actor who may not.
"""

from datetime import timedelta

import pytest
from django.utils import timezone

from accounts.models import ContactMethod, ContactType, GameAccount, User
from teams import services as team_services
from tournaments import registration as reg
from tournaments.models import (
    ActorType,
    RegistrationAction,
    RegistrationStatus,
    ReviewMode,
    Tournament,
    TournamentStatus,
)

LOCAL, UPSTREAM, TWO_STAGE = ReviewMode.LOCAL, ReviewMode.UPSTREAM, ReviewMode.TWO_STAGE
PENDING = RegistrationStatus.PENDING
AWAITING = RegistrationStatus.AWAITING_UPSTREAM
APPROVED = RegistrationStatus.APPROVED
REJECTED = RegistrationStatus.REJECTED
WITHDRAWN = RegistrationStatus.WITHDRAWN


def player(email, nickname):
    now = timezone.now()
    user = User.objects.create_user(
        email=email,
        password="Correct-Horse-Battery-1",
        nickname=nickname,
        is_sjtu=True,
        agreed_terms_at=now,
        agreed_cross_border_at=now,
    )
    GameAccount.objects.create(user=user, battletag=f"{nickname}#7000", rank_damage=20)
    ContactMethod.objects.create(user=user, type=ContactType.QQ, value="123456789")
    return user


def admin_user(email=None):
    email = email or f"table-admin{User.objects.count()}@example.com"
    return User.objects.create_user(
        email=email,
        password="Correct-Horse-Battery-1",
        nickname="赛事管理员",
        agreed_terms_at=timezone.now(),
        agreed_cross_border_at=timezone.now(),
    )


@pytest.fixture
def make(db):
    """Build a fresh registration in a given review mode, in a given state."""
    counter = {"n": 0}

    def build(mode=LOCAL, status=PENDING):
        counter["n"] += 1
        index = counter["n"]
        now = timezone.now()
        tournament = Tournament.objects.create(
            title=f"状态表赛事{index}",
            registration_opens_at=now - timedelta(days=1),
            registration_closes_at=now + timedelta(days=7),
            roster_min=2,
            roster_max=3,
            status=TournamentStatus.PUBLISHED,
            published_at=now,
            review_mode=mode,
        )
        captain = player(f"cap{index}@example.com", f"队长{index}")
        mate = player(f"mate{index}@example.com", f"队员{index}")
        team = team_services.create_team(user=captain, name=f"状态表战队{index}")
        application = team_services.apply_to_team(
            team=team, user=mate, roles={"tank": True}
        )
        team_services.approve_application(application=application, actor=captain)
        selections = {
            str(membership.user.pk): membership.user.game_accounts.first().pk
            for membership in team.memberships.all()
        }
        registration = reg.submit(
            tournament=tournament, team=team, actor=captain, selections=selections
        )
        if status != PENDING:
            _force(registration, status)
        return registration, captain, team, selections

    return build


def _force(registration, status):
    """Put a registration into a state without going through the service."""
    from tournaments.models import ACTIVE_STATUSES, Registration

    Registration.objects.filter(pk=registration.pk).update(status=status)
    registration.refresh_from_db()
    registration.members.update(is_active=status in ACTIVE_STATUSES)


# --- row 1: 待审核 → 通过 → 已通过 ------------------------------------------------


@pytest.mark.django_db
def test_local_admin_approves_a_pending_registration(make):
    registration, *_ = make(LOCAL, PENDING)

    reg.approve(registration=registration, actor=admin_user())

    registration.refresh_from_db()
    assert registration.status == APPROVED


@pytest.mark.django_db
def test_upstream_approves_a_pending_registration(make):
    registration, *_ = make(UPSTREAM, PENDING)

    reg.approve(registration=registration, actor=None, actor_type=ActorType.UPSTREAM)

    registration.refresh_from_db()
    assert registration.status == APPROVED


@pytest.mark.django_db
def test_a_local_admin_may_not_approve_in_upstream_mode(make):
    registration, *_ = make(UPSTREAM, PENDING)

    with pytest.raises(reg.RegistrationError, match="本站不能改状态"):
        reg.approve(registration=registration, actor=admin_user())


@pytest.mark.django_db
def test_an_upstream_may_not_approve_in_local_mode(make):
    """Round 018 found this one missing."""
    registration, *_ = make(LOCAL, PENDING)

    with pytest.raises(reg.RegistrationError, match="上游不能改状态"):
        reg.approve(
            registration=registration, actor=None, actor_type=ActorType.UPSTREAM
        )


# --- row 2: 待审核 → 通过 → 待上游确认（两级审核）-----------------------------------


@pytest.mark.django_db
def test_two_stage_local_approval_waits_for_the_upstream(make):
    registration, *_ = make(TWO_STAGE, PENDING)

    reg.approve(registration=registration, actor=admin_user())

    registration.refresh_from_db()
    assert registration.status == AWAITING


@pytest.mark.django_db
def test_two_stage_upstream_may_not_skip_the_local_stage(make):
    """Round 018 found this one too."""
    registration, *_ = make(TWO_STAGE, PENDING)

    with pytest.raises(reg.RegistrationError, match="先由本站管理员审核"):
        reg.approve(
            registration=registration, actor=None, actor_type=ActorType.UPSTREAM
        )


# --- row 3: 待审核 → 驳回 → 已驳回 ------------------------------------------------


@pytest.mark.django_db
@pytest.mark.parametrize("mode", [LOCAL, TWO_STAGE])
def test_a_local_admin_rejects_a_pending_registration(make, mode):
    registration, *_ = make(mode, PENDING)

    reg.reject(registration=registration, actor=admin_user(), note="名单不齐")

    registration.refresh_from_db()
    assert registration.status == REJECTED
    assert registration.status_note == "名单不齐"


@pytest.mark.django_db
def test_the_upstream_rejects_a_pending_registration_in_upstream_mode(make):
    registration, *_ = make(UPSTREAM, PENDING)

    reg.reject(
        registration=registration,
        actor=None,
        note="不符合要求",
        actor_type=ActorType.UPSTREAM,
    )

    registration.refresh_from_db()
    assert registration.status == REJECTED


# --- row 4 and 5: 待上游确认 → 确认 / 驳回 ------------------------------------------


@pytest.mark.django_db
def test_the_upstream_confirms_an_awaiting_registration(make):
    registration, *_ = make(TWO_STAGE, AWAITING)

    reg.approve(registration=registration, actor=None, actor_type=ActorType.UPSTREAM)

    registration.refresh_from_db()
    assert registration.status == APPROVED


@pytest.mark.django_db
def test_the_upstream_rejects_an_awaiting_registration(make):
    registration, *_ = make(TWO_STAGE, AWAITING)

    reg.reject(
        registration=registration,
        actor=None,
        note="上游不同意",
        actor_type=ActorType.UPSTREAM,
    )

    registration.refresh_from_db()
    assert registration.status == REJECTED


@pytest.mark.django_db
def test_a_local_admin_may_not_confirm_an_awaiting_registration(make):
    """Design 8.5: 待上游确认 is the upstream's step, in every mode."""
    registration, *_ = make(TWO_STAGE, AWAITING)

    with pytest.raises(reg.RegistrationError, match="上游"):
        reg.approve(registration=registration, actor=admin_user())


# --- row 6: 已通过 → 撤销通过 → 已驳回 --------------------------------------------


@pytest.mark.django_db
def test_a_local_admin_revokes_in_local_mode(make):
    registration, *_ = make(LOCAL, APPROVED)

    reg.reject(registration=registration, actor=admin_user(), note="资格有问题")

    registration.refresh_from_db()
    assert registration.status == REJECTED
    entry = registration.logs.order_by("-id").first()
    assert entry.action == RegistrationAction.REVOKE


@pytest.mark.django_db
@pytest.mark.parametrize("mode", [UPSTREAM, TWO_STAGE])
def test_the_upstream_revokes_in_upstream_and_two_stage_modes(make, mode):
    registration, *_ = make(mode, APPROVED)

    reg.reject(
        registration=registration,
        actor=None,
        note="上游撤销",
        actor_type=ActorType.UPSTREAM,
    )

    registration.refresh_from_db()
    assert registration.status == REJECTED
    assert registration.logs.order_by("-id").first().action == (
        RegistrationAction.REVOKE
    )


@pytest.mark.django_db
@pytest.mark.parametrize("mode", [UPSTREAM, TWO_STAGE])
def test_a_local_admin_may_not_revoke_outside_local_mode(make, mode):
    """Design 8.5 row 6: revoking belongs to the upstream in those modes."""
    registration, *_ = make(mode, APPROVED)

    with pytest.raises(reg.RegistrationError):
        reg.reject(registration=registration, actor=admin_user(), note="本站撤销")


@pytest.mark.django_db
def test_rejecting_and_revoking_both_need_a_note(make):
    for status in (PENDING, APPROVED):
        registration, *_ = make(LOCAL, status)
        with pytest.raises(reg.RegistrationError, match="备注"):
            reg.reject(registration=registration, actor=admin_user(), note="   ")


# --- row 7: 三种状态都可以撤回 -----------------------------------------------------


@pytest.mark.django_db
@pytest.mark.parametrize(
    ("mode", "status"),
    [(LOCAL, PENDING), (TWO_STAGE, AWAITING), (LOCAL, APPROVED)],
)
def test_the_captain_withdraws_from_every_active_state(make, mode, status):
    registration, captain, *_ = make(mode, status)

    reg.withdraw(registration=registration, actor=captain)

    registration.refresh_from_db()
    assert registration.status == WITHDRAWN
    # Design 8.5: a withdrawn roster stops occupying places.
    assert not registration.members.filter(is_active=True).exists()


@pytest.mark.django_db
@pytest.mark.parametrize("status", [REJECTED, WITHDRAWN])
def test_an_inactive_registration_cannot_be_withdrawn_again(make, status):
    registration, captain, *_ = make(LOCAL, status)

    with pytest.raises(reg.RegistrationError, match="当前状态不能撤回"):
        reg.withdraw(registration=registration, actor=captain)


# --- row 8: 三种状态都可以同步名单 --------------------------------------------------


@pytest.mark.django_db
@pytest.mark.parametrize(
    ("mode", "status"),
    [(LOCAL, PENDING), (TWO_STAGE, AWAITING), (LOCAL, APPROVED)],
)
def test_syncing_returns_to_pending_and_bumps_the_version(make, mode, status):
    registration, captain, team, selections = make(mode, status)
    before = registration.roster_version

    reg.submit(
        tournament=registration.tournament,
        team=team,
        actor=captain,
        selections=selections,
    )

    registration.refresh_from_db()
    assert registration.status == PENDING
    assert registration.roster_version == before + 1
    entry = registration.logs.order_by("-id").first()
    assert entry.action == RegistrationAction.SYNC_ROSTER
    # Design 8.5: the log keeps the whole new roster, for tracing.
    assert entry.roster_snapshot
    assert len(entry.roster_snapshot) == registration.members.count()


# --- row 9: 已驳回 / 已撤回 可以重新提交 ---------------------------------------------


@pytest.mark.django_db
@pytest.mark.parametrize("status", [REJECTED, WITHDRAWN])
def test_resubmitting_reuses_the_record_and_bumps_the_version(make, status):
    registration, captain, team, selections = make(LOCAL, status)
    before = registration.roster_version

    again = reg.submit(
        tournament=registration.tournament,
        team=team,
        actor=captain,
        selections=selections,
    )

    assert again.pk == registration.pk  # design 8.5: the same record
    again.refresh_from_db()
    assert again.status == PENDING
    assert again.roster_version == before + 1
    assert again.logs.order_by("-id").first().action == RegistrationAction.RESUBMIT


# --- the notes at the bottom of 8.5 -----------------------------------------------


@pytest.mark.django_db
def test_admins_and_upstreams_are_not_bound_by_the_deadline(make):
    """Design 8.5: only the captain is stopped once registration closes."""
    registration, captain, *_ = make(LOCAL, PENDING)
    Tournament.objects.filter(pk=registration.tournament_id).update(
        registration_closes_at=timezone.now() - timedelta(hours=1)
    )
    registration.refresh_from_db()

    with pytest.raises(reg.RegistrationError, match="报名已截止"):
        reg.withdraw(registration=registration, actor=captain)

    reg.approve(registration=registration, actor=admin_user())
    registration.refresh_from_db()
    assert registration.status == APPROVED


@pytest.mark.django_db
def test_every_transition_writes_a_log_line(make):
    """Design 8.5: before and after status, actor type, version, note, time."""
    registration, captain, *_ = make(LOCAL, PENDING)
    start = registration.logs.count()

    reg.approve(registration=registration, actor=admin_user())
    reg.reject(registration=registration, actor=admin_user(), note="撤销掉")

    entries = list(registration.logs.order_by("id")[start:])
    assert len(entries) == 2
    for entry in entries:
        assert entry.to_status
        assert entry.actor_type
        assert entry.roster_version == registration.roster_version
        assert entry.created_at
    assert entries[0].from_status == PENDING
    assert entries[1].note == "撤销掉"
