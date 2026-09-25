"""Design 8.5's state transition table, walked row by row.

Round 015 covered the eight submission checks and the common flows; round
033 walked the nine-row table with three review modes. Round 067 removed
the upstream: this is the six-row table that remains, plus the
「报名自动通过」 switch (design 8.1, 8.3, 8.4), which lets the system approve
inside the submit transaction.
"""

from datetime import timedelta

import pytest
from django.core import mail
from django.utils import timezone

from accounts.models import ContactMethod, ContactType, GameAccount, User
from teams import services as team_services
from tournaments import registration as reg
from tournaments.models import (
    ActorType,
    RegistrationAction,
    RegistrationStatus,
    Tournament,
    TournamentStatus,
)

PENDING = RegistrationStatus.PENDING
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
    """Build a fresh registration, in a given state, on a fresh tournament."""
    counter = {"n": 0}

    def build(status=None, *, auto_approve=False):
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
            auto_approve=auto_approve,
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
        if status is not None and status != registration.status:
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
def test_an_admin_approves_a_pending_registration(make):
    registration, *_ = make(PENDING)

    reg.approve(registration=registration, actor=admin_user())

    registration.refresh_from_db()
    assert registration.status == APPROVED
    entry = registration.logs.order_by("-id").first()
    assert entry.actor_type == ActorType.ADMIN


@pytest.mark.django_db
@pytest.mark.parametrize("status", [APPROVED, REJECTED, WITHDRAWN])
def test_only_a_pending_registration_can_be_approved(make, status):
    registration, *_ = make(status)

    with pytest.raises(reg.RegistrationError, match="当前状态不能通过"):
        reg.approve(registration=registration, actor=admin_user())

    registration.refresh_from_db()
    assert registration.status == status


# --- row 2: 待审核 → 驳回 → 已驳回 ------------------------------------------------


@pytest.mark.django_db
def test_an_admin_rejects_a_pending_registration(make):
    registration, *_ = make(PENDING)

    reg.reject(registration=registration, actor=admin_user(), note="名单不齐")

    registration.refresh_from_db()
    assert registration.status == REJECTED
    assert registration.status_note == "名单不齐"
    assert registration.logs.order_by("-id").first().action == (
        RegistrationAction.REJECT
    )


# --- row 3: 已通过 → 撤销通过 → 已驳回 --------------------------------------------


@pytest.mark.django_db
def test_an_admin_revokes_an_approval(make):
    registration, *_ = make(APPROVED)

    reg.reject(registration=registration, actor=admin_user(), note="资格有问题")

    registration.refresh_from_db()
    assert registration.status == REJECTED
    entry = registration.logs.order_by("-id").first()
    assert entry.action == RegistrationAction.REVOKE


@pytest.mark.django_db
@pytest.mark.parametrize("status", [REJECTED, WITHDRAWN])
def test_an_inactive_registration_cannot_be_rejected(make, status):
    registration, *_ = make(status)

    with pytest.raises(reg.RegistrationError, match="当前状态不能驳回"):
        reg.reject(registration=registration, actor=admin_user(), note="再驳一次")


@pytest.mark.django_db
def test_rejecting_and_revoking_both_need_a_note(make):
    for status in (PENDING, APPROVED):
        registration, *_ = make(status)
        with pytest.raises(reg.RegistrationError, match="备注"):
            reg.reject(registration=registration, actor=admin_user(), note="   ")


# --- row 4: 两种状态都可以撤回 -----------------------------------------------------


@pytest.mark.django_db
@pytest.mark.parametrize("status", [PENDING, APPROVED])
def test_the_captain_withdraws_from_every_active_state(make, status):
    registration, captain, *_ = make(status)

    reg.withdraw(registration=registration, actor=captain)

    registration.refresh_from_db()
    assert registration.status == WITHDRAWN
    # Design 8.5: a withdrawn roster stops occupying places.
    assert not registration.members.filter(is_active=True).exists()


@pytest.mark.django_db
@pytest.mark.parametrize("status", [REJECTED, WITHDRAWN])
def test_an_inactive_registration_cannot_be_withdrawn_again(make, status):
    registration, captain, *_ = make(status)

    with pytest.raises(reg.RegistrationError, match="当前状态不能撤回"):
        reg.withdraw(registration=registration, actor=captain)


# --- row 5: 两种状态都可以同步名单 --------------------------------------------------


@pytest.mark.django_db
@pytest.mark.parametrize("status", [PENDING, APPROVED])
def test_syncing_returns_to_pending_and_bumps_the_version(make, status):
    registration, captain, team, selections = make(status)
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


# --- row 6: 已驳回 / 已撤回 可以重新提交 ---------------------------------------------


@pytest.mark.django_db
@pytest.mark.parametrize("status", [REJECTED, WITHDRAWN])
def test_resubmitting_reuses_the_record_and_bumps_the_version(make, status):
    registration, captain, team, selections = make(status)
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
def test_admins_are_not_bound_by_the_deadline(make):
    """Design 8.5: only the captain is stopped once registration closes."""
    registration, captain, *_ = make(PENDING)
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
    registration, captain, *_ = make(PENDING)
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


# --- 报名自动通过（design 8.1, 8.3, 8.4）---------------------------------------------


@pytest.mark.django_db
def test_auto_approve_passes_the_registration_on_submit(make):
    registration, *_ = make(auto_approve=True)

    assert registration.status == APPROVED
    assert registration.members.filter(is_active=True).count() == 2
    entries = list(registration.logs.order_by("id"))
    assert [entry.action for entry in entries] == [
        RegistrationAction.SUBMIT,
        RegistrationAction.APPROVE,
    ]
    assert entries[0].actor_type == ActorType.CAPTAIN
    assert entries[1].actor_type == ActorType.SYSTEM
    assert entries[1].actor_user is None
    assert entries[1].note == reg.AUTO_APPROVE_NOTE
    assert (entries[1].from_status, entries[1].to_status) == (PENDING, APPROVED)


@pytest.mark.django_db
def test_without_the_switch_a_submission_waits_for_review(make):
    registration, *_ = make()

    assert registration.status == PENDING
    assert registration.logs.count() == 1


@pytest.mark.django_db
def test_auto_approve_sends_one_mail_saying_approved(
    make, django_capture_on_commit_callbacks
):
    """Design 8.3: one mail, not a 「提交」 mail plus a 「状态变化」 mail."""
    mail.outbox.clear()
    with django_capture_on_commit_callbacks(execute=True):
        registration, *_ = make(auto_approve=True)

    # The fixture also builds the team, whose application mails land here too.
    about_registration = [m for m in mail.outbox if "报名" in m.subject]
    assert [m.subject for m in about_registration] == ["报名已提交"]
    assert "已通过" in about_registration[0].body


@pytest.mark.django_db
def test_an_admin_approval_still_sends_the_status_mail(
    make, django_capture_on_commit_callbacks
):
    registration, *_ = make(PENDING)
    mail.outbox.clear()
    with django_capture_on_commit_callbacks(execute=True):
        reg.approve(registration=registration, actor=admin_user())

    assert [message.subject for message in mail.outbox] == ["报名状态有更新"]


@pytest.mark.django_db
def test_syncing_an_auto_approved_roster_is_approved_again(make):
    """Design 8.4: the sync goes back to pending and the switch passes it."""
    registration, captain, team, selections = make(auto_approve=True)

    reg.submit(
        tournament=registration.tournament,
        team=team,
        actor=captain,
        selections=selections,
    )

    registration.refresh_from_db()
    assert registration.status == APPROVED
    assert registration.roster_version == 2
    actions = list(registration.logs.order_by("id").values_list("action", flat=True))
    assert actions == [
        RegistrationAction.SUBMIT,
        RegistrationAction.APPROVE,
        RegistrationAction.SYNC_ROSTER,
        RegistrationAction.APPROVE,
    ]


@pytest.mark.django_db
def test_an_admin_can_still_revoke_an_automatic_approval(make):
    registration, *_ = make(auto_approve=True)

    reg.reject(registration=registration, actor=admin_user(), note="资格不符")

    registration.refresh_from_db()
    assert registration.status == REJECTED
    assert registration.logs.order_by("-id").first().action == (
        RegistrationAction.REVOKE
    )


@pytest.mark.django_db
def test_auto_approve_is_locked_once_anyone_has_registered(make):
    """Design 8.1: the switch cannot change after the first registration.

    Round 067 found the old 「审核模式」 lock was enforced only by the API;
    the admin form never checked. The form is what locks it now.
    """
    from tournaments.wagtail_hooks import TournamentAdminForm, TournamentViewSet

    registration, *_ = make(PENDING)
    tournament = registration.tournament
    data = {
        "title": tournament.title,
        "summary": "",
        "starts_at": "",
        "registration_opens_at": tournament.registration_opens_at.strftime(
            "%Y-%m-%d %H:%M"
        ),
        "registration_closes_at": tournament.registration_closes_at.strftime(
            "%Y-%m-%d %H:%M"
        ),
        "roster_min": tournament.roster_min,
        "roster_max": tournament.roster_max,
        "sjtu_only": False,
        "auto_approve": True,
    }

    form_class = TournamentViewSet().get_form_class(for_update=True)
    assert issubclass(form_class, TournamentAdminForm)  # the lock is wired in
    form = form_class(data, instance=tournament)

    assert not form.is_valid()
    assert "auto_approve" in form.errors
    assert "已经有报名" in form.errors["auto_approve"][0]


@pytest.mark.django_db
def test_auto_approve_can_change_while_nobody_has_registered(db):
    from tournaments.wagtail_hooks import TournamentAdminForm, TournamentViewSet

    now = timezone.now()
    tournament = Tournament.objects.create(
        title="还没人报名",
        registration_opens_at=now - timedelta(days=1),
        registration_closes_at=now + timedelta(days=7),
        roster_min=2,
        roster_max=3,
    )
    data = {
        "title": tournament.title,
        "summary": "",
        "starts_at": "",
        "registration_opens_at": tournament.registration_opens_at.strftime(
            "%Y-%m-%d %H:%M"
        ),
        "registration_closes_at": tournament.registration_closes_at.strftime(
            "%Y-%m-%d %H:%M"
        ),
        "roster_min": tournament.roster_min,
        "roster_max": tournament.roster_max,
        "sjtu_only": False,
        "auto_approve": True,
    }

    form_class = TournamentViewSet().get_form_class(for_update=True)
    assert issubclass(form_class, TournamentAdminForm)  # the lock is wired in
    form = form_class(data, instance=tournament)

    assert form.is_valid(), form.errors
