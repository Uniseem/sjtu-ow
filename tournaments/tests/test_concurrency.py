"""Design 12.12: IMMEDIATE transactions, and what that is supposed to buy.

The design's claim is specific: because every write transaction takes the
whole-database lock up front, "check then write" is serialised and two
requests cannot both pass the same check. Round 015 verified the database
constraint by calling the code twice in a row, which does not exercise that
claim at all — sequential calls would pass even with no locking whatsoever.

These tests use real threads and real connections.
"""

import threading
from datetime import timedelta

import pytest
from django.db import IntegrityError, connections
from django.utils import timezone

from accounts.models import ContactMethod, ContactType, GameAccount, User
from teams import services as team_services
from tournaments import registration as reg
from tournaments.models import (
    Registration,
    RegistrationMember,
    RegistrationStatus,
    Tournament,
    TournamentStatus,
)


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
    GameAccount.objects.create(user=user, battletag=f"{nickname}#8000", rank_damage=20)
    ContactMethod.objects.create(user=user, type=ContactType.QQ, value="123456789")
    return user


def run_together(targets):
    """Start every callable at the same moment; collect outcomes in order."""
    start = threading.Barrier(len(targets))
    results = [None] * len(targets)

    def wrap(index, fn):
        def inner():
            start.wait()
            try:
                results[index] = ("ok", fn())
            except Exception as exc:  # noqa: BLE001 — the exception is the result
                results[index] = ("error", exc)
            finally:
                connections.close_all()

        return inner

    threads = [
        threading.Thread(target=wrap(index, fn)) for index, fn in enumerate(targets)
    ]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join(timeout=30)
    assert all(not thread.is_alive() for thread in threads), "有线程卡住了"
    return results


@pytest.mark.django_db(transaction=True)
def test_two_captains_cannot_both_claim_the_same_player():
    """Design 8.3 check 8 plus 12.12: the shared player lands on one roster.

    Both teams pass the application-level check at the same instant; only the
    write order decides. If IMMEDIATE did not serialise, both would commit and
    the player would occupy two rosters in one tournament.
    """
    now = timezone.now()
    tournament = Tournament.objects.create(
        title="并发赛事",
        registration_opens_at=now - timedelta(days=1),
        registration_closes_at=now + timedelta(days=7),
        roster_min=2,
        roster_max=3,
        status=TournamentStatus.PUBLISHED,
        published_at=now,
    )
    shared = player("shared@example.com", "两队都要的人")
    builds = []
    for index in (1, 2):
        captain = player(f"cap{index}@example.com", f"队长{index}")
        team = team_services.create_team(user=captain, name=f"并发战队{index}")
        application = team_services.apply_to_team(
            team=team, user=shared, roles={"damage": True}
        )
        team_services.approve_application(application=application, actor=captain)
        selections = {
            str(membership.user.pk): membership.user.game_accounts.first().pk
            for membership in team.memberships.all()
        }
        builds.append((team, captain, selections))

    def submit(team, captain, selections):
        def inner():
            return reg.submit(
                tournament=tournament,
                team=team,
                actor=captain,
                selections=selections,
            )

        return inner

    results = run_together([submit(*build) for build in builds])

    succeeded = [state for state, _payload in results if state == "ok"]
    assert len(succeeded) == 1, f"应该只有一个成功，实际 {results}"
    # And the database agrees: the shared player is on exactly one roster.
    active = RegistrationMember.objects.filter(
        tournament=tournament, user=shared, is_active=True
    )
    assert active.count() == 1
    assert Registration.objects.filter(tournament=tournament).count() == 1

    failure = next(payload for state, payload in results if state == "error")
    assert isinstance(failure, reg.RegistrationError | IntegrityError)


@pytest.mark.django_db(transaction=True)
def test_a_team_cannot_go_over_capacity_under_a_race():
    """Design 12.12: approving two applications at once is serialised.

    The team has one place left and two pending applications. Both approvals
    read "there is room" before either writes.
    """
    from core.models import SiteSettings
    from teams.models import TeamMembership

    site = SiteSettings.load()
    site.team_max_members = 3
    site.save()

    captain = player("race-cap@example.com", "队长")
    team = team_services.create_team(user=captain, name="满员测试战队")
    filler = player("race-filler@example.com", "已在队里")
    team_services.approve_application(
        application=team_services.apply_to_team(
            team=team, user=filler, roles={"tank": True}
        ),
        actor=captain,
    )
    assert team.memberships.count() == 2  # one place left

    applications = [
        team_services.apply_to_team(
            team=team,
            user=player(f"race{index}@example.com", f"申请人{index}"),
            roles={"damage": True},
        )
        for index in (1, 2)
    ]

    def approve(application):
        def inner():
            return team_services.approve_application(
                application=application, actor=captain
            )

        return inner

    results = run_together([approve(app) for app in applications])

    succeeded = [state for state, _payload in results if state == "ok"]
    assert len(succeeded) == 1, f"队伍只剩一个位置，实际 {results}"
    assert TeamMembership.objects.filter(team=team).count() == 3


@pytest.mark.django_db(transaction=True)
def test_reads_are_not_blocked_while_a_write_is_in_flight():
    """Design 12.13: WAL means readers and the writer do not block each other."""
    from django.db import transaction

    now = timezone.now()
    Tournament.objects.create(
        title="WAL 读写赛事",
        registration_opens_at=now - timedelta(days=1),
        registration_closes_at=now + timedelta(days=7),
        status=TournamentStatus.PUBLISHED,
        published_at=now,
    )
    writing = threading.Event()
    may_finish = threading.Event()
    read_done = threading.Event()

    def slow_writer():
        try:
            with transaction.atomic():
                Tournament.objects.filter(title="WAL 读写赛事").update(
                    summary="写事务进行中"
                )
                writing.set()
                may_finish.wait(timeout=10)
        finally:
            connections.close_all()

    def reader():
        try:
            writing.wait(timeout=10)
            # This must not block behind the open write transaction.
            assert Tournament.objects.filter(status=TournamentStatus.PUBLISHED).count()
            read_done.set()
        finally:
            connections.close_all()

    writer_thread = threading.Thread(target=slow_writer)
    reader_thread = threading.Thread(target=reader)
    writer_thread.start()
    reader_thread.start()
    finished_in_time = read_done.wait(timeout=5)
    may_finish.set()
    writer_thread.join(timeout=10)
    reader_thread.join(timeout=10)

    assert finished_in_time, "写事务进行中时读被阻塞了，WAL 没有生效"


@pytest.mark.django_db(transaction=True)
def test_many_simultaneous_submissions_all_land():
    """Ten captains submitting at once: every one either commits or says why.

    Design 15.1 assumes 200 concurrent visitors; this is about whether the
    whole-database write lock degrades into errors under a burst, or just
    queues. With timeout=5 it should queue.
    """
    now = timezone.now()
    tournament = Tournament.objects.create(
        title="并发提交赛事",
        registration_opens_at=now - timedelta(days=1),
        registration_closes_at=now + timedelta(days=7),
        roster_min=2,
        roster_max=3,
        status=TournamentStatus.PUBLISHED,
        published_at=now,
    )
    builds = []
    for index in range(10):
        captain = player(f"burst-cap{index}@example.com", f"爆发队长{index}")
        mate = player(f"burst-mate{index}@example.com", f"爆发队员{index}")
        team = team_services.create_team(user=captain, name=f"爆发战队{index}")
        team_services.approve_application(
            application=team_services.apply_to_team(
                team=team, user=mate, roles={"tank": True}
            ),
            actor=captain,
        )
        selections = {
            str(membership.user.pk): membership.user.game_accounts.first().pk
            for membership in team.memberships.all()
        }
        builds.append((team, captain, selections))

    def submit(team, captain, selections):
        def inner():
            return reg.submit(
                tournament=tournament,
                team=team,
                actor=captain,
                selections=selections,
            )

        return inner

    results = run_together([submit(*build) for build in builds])

    errors = [payload for state, payload in results if state == "error"]
    assert not errors, f"并发提交出现错误：{errors}"
    assert Registration.objects.filter(tournament=tournament).count() == 10
    assert (
        Registration.objects.filter(
            tournament=tournament, status=RegistrationStatus.PENDING
        ).count()
        == 10
    )
