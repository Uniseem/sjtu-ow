"""Design 8.8.2: admins form ad-hoc teams from the pool (round 070).

The board posts a layout; ``form_teams`` validates all of it before writing
anything. Members may leave before the deadline; admins may dissolve.
"""

import re
from datetime import timedelta

import pytest
from django.contrib.auth.models import Group
from django.core import mail
from django.core.management import call_command
from django.urls import reverse
from django.utils import timezone

from accounts.models import ContactMethod, User
from core.models import PrerenderedPage
from teams import services as team_services
from tournaments import registration as reg
from tournaments.models import (
    ActorType,
    IndividualSignup,
    Registration,
    RegistrationAction,
    RegistrationStatus,
    Tournament,
    TournamentStatus,
)
from tournaments.tests.test_state_table import player

APPROVED = RegistrationStatus.APPROVED
WITHDRAWN = RegistrationStatus.WITHDRAWN


def _tournament(**kwargs):
    now = timezone.now()
    options = {
        "title": "新生杯",
        "registration_opens_at": now - timedelta(days=1),
        "registration_closes_at": now + timedelta(days=7),
        "roster_min": 2,
        "roster_max": 3,
        "status": TournamentStatus.PUBLISHED,
        "published_at": now,
        "allow_individual_signup": True,
    }
    options.update(kwargs)
    return Tournament.objects.create(**options)


def _pool(tournament, count, prefix="散人"):
    entries = []
    for index in range(count):
        user = player(f"{prefix}{index}@example.com", f"{prefix}{index}")
        entries.append(
            reg.sign_up_individual(
                tournament=tournament,
                user=user,
                game_account_id=user.game_accounts.first().pk,
                roles=["tank"],
            )
        )
    return entries


def _admin():
    index = User.objects.count()
    return player(f"board-admin{index}@example.com", f"编排管理员{index}")


def _layout(*teams, **named):
    """(name, [entries]) tuples become a layout for a new team each."""
    layout = []
    for name, entries in teams:
        layout.append(
            {
                "registration_id": None,
                "name": name,
                "signup_ids": [entry.pk for entry in entries],
            }
        )
    assert not named
    return layout


def _existing(registration, name, entries):
    return {
        "registration_id": registration.pk,
        "name": name,
        "signup_ids": [entry.pk for entry in entries],
    }


@pytest.fixture
def prerender_on(settings, tmp_path):
    settings.PRERENDER_ENABLED = True
    settings.PRERENDER_ROOT = tmp_path


# --- forming a team ---------------------------------------------------------------


@pytest.mark.django_db
def test_forming_a_team_registers_it_as_approved(django_capture_on_commit_callbacks):
    tournament = _tournament()
    entries = _pool(tournament, 2)
    admin = _admin()
    mail.outbox.clear()

    with django_capture_on_commit_callbacks(execute=True):
        result = reg.form_teams(
            tournament=tournament, actor=admin, layout=_layout(("一队", entries))
        )

    assert result == {"created": 1, "updated": 0, "dissolved": 0, "returned": 0}
    registration = tournament.registrations.get()
    assert registration.team is None and registration.is_adhoc
    assert registration.team_name == "一队"
    assert registration.status == APPROVED
    assert registration.submitted_by == admin
    members = list(registration.members.order_by("id"))
    assert [row.user for row in members] == [entry.user for entry in entries]
    assert all(row.is_active and not row.is_captain for row in members)
    assert members[0].battletag == entries[0].game_account.battletag
    entry = IndividualSignup.objects.get(pk=entries[0].pk)
    assert entry.registration == registration and entry.is_placed
    log = registration.logs.get()
    assert (log.action, log.actor_type, log.actor_user) == (
        RegistrationAction.FORM_TEAM,
        ActorType.ADMIN,
        admin,
    )
    assert log.roster_snapshot and len(log.roster_snapshot) == 2
    # Design 10.2: one mail per member, nothing else.
    assert sorted(m.to[0] for m in mail.outbox) == sorted(e.user.email for e in entries)
    assert all(m.subject == "已编入临时队伍" for m in mail.outbox)


@pytest.mark.django_db
def test_the_formed_team_shows_on_the_tournament_page_without_a_link(client):
    tournament = _tournament()
    entries = _pool(tournament, 2)
    reg.form_teams(
        tournament=tournament, actor=_admin(), layout=_layout(("一队", entries))
    )

    html = client.get(tournament.get_absolute_url()).content.decode()

    assert "一队" in html
    assert "临时队伍" in html
    assert re.search(r'href="/teams/\d+/"', html) is None  # no team page to link
    assert "还没有人个人报名" in html  # everyone was placed


@pytest.mark.django_db
def test_a_formed_team_never_appears_in_the_team_list(client):
    tournament = _tournament()
    entries = _pool(tournament, 2)
    reg.form_teams(
        tournament=tournament, actor=_admin(), layout=_layout(("一队", entries))
    )

    assert "一队" not in client.get(reverse("team_index")).content.decode()


# --- every refusal ------------------------------------------------------------------


@pytest.mark.django_db
def test_a_team_over_the_maximum_is_refused_and_nothing_is_written():
    tournament = _tournament(roster_max=2)
    entries = _pool(tournament, 3)

    with pytest.raises(reg.RegistrationError, match="超过上限"):
        reg.form_teams(
            tournament=tournament, actor=_admin(), layout=_layout(("超员", entries))
        )

    assert not tournament.registrations.exists()
    assert not IndividualSignup.objects.filter(registration__isnull=False).exists()


@pytest.mark.django_db
@pytest.mark.parametrize("name", ["", "   ", "一二三四五六七八九十一二三四五六七"])
def test_a_bad_name_is_refused(name):
    tournament = _tournament()
    entries = _pool(tournament, 2)

    with pytest.raises(reg.RegistrationError, match="队"):
        reg.form_teams(
            tournament=tournament, actor=_admin(), layout=_layout((name, entries))
        )
    assert not tournament.registrations.exists()


@pytest.mark.django_db
def test_a_name_taken_by_a_live_registration_is_refused():
    tournament = _tournament()
    captain = player("named-cap@example.com", "有队的")
    mate = player("named-mate@example.com", "有队的队友")
    team = team_services.create_team(user=captain, name="老牌战队")
    application = team_services.apply_to_team(
        team=team, user=mate, roles={"tank": True}
    )
    team_services.approve_application(application=application, actor=captain)
    reg.submit(
        tournament=tournament,
        team=team,
        actor=captain,
        selections={
            str(m.user.pk): m.user.game_accounts.first().pk
            for m in team.memberships.all()
        },
    )
    entries = _pool(tournament, 2)

    with pytest.raises(reg.RegistrationError, match="已经有了"):
        reg.form_teams(
            tournament=tournament, actor=_admin(), layout=_layout(("老牌战队", entries))
        )


@pytest.mark.django_db
def test_two_new_teams_cannot_share_a_name():
    tournament = _tournament()
    entries = _pool(tournament, 4)

    with pytest.raises(reg.RegistrationError, match="同名"):
        reg.form_teams(
            tournament=tournament,
            actor=_admin(),
            layout=_layout(("同名", entries[:2]), ("同名", entries[2:])),
        )


@pytest.mark.django_db
def test_a_person_in_two_teams_is_refused():
    tournament = _tournament()
    entries = _pool(tournament, 3)

    with pytest.raises(reg.RegistrationError, match="两支队伍"):
        reg.form_teams(
            tournament=tournament,
            actor=_admin(),
            layout=_layout(("一队", entries[:2]), ("二队", [entries[1], entries[2]])),
        )


@pytest.mark.django_db
def test_an_entry_from_another_tournament_is_refused():
    tournament = _tournament()
    other = _tournament(title="别的赛事")
    entries = _pool(tournament, 1) + _pool(other, 1, prefix="别处")

    with pytest.raises(reg.RegistrationError, match="不属于这项赛事"):
        reg.form_teams(
            tournament=tournament, actor=_admin(), layout=_layout(("混", entries))
        )


@pytest.mark.django_db
def test_someone_who_joined_a_real_roster_cannot_be_placed():
    """Design 8.8.2: they stay in the pool, flagged, until they leave that team."""
    tournament = _tournament()
    entries = _pool(tournament, 2)
    stray = entries[0]
    captain = player("late-cap@example.com", "后来的队长")
    team = team_services.create_team(user=captain, name="后来的战队")
    application = team_services.apply_to_team(
        team=team, user=stray.user, roles={"tank": True}
    )
    team_services.approve_application(application=application, actor=captain)
    reg.submit(
        tournament=tournament,
        team=team,
        actor=captain,
        selections={
            str(m.user.pk): m.user.game_accounts.first().pk
            for m in team.memberships.all()
        },
    )

    assert "名单中" in reg.pool_entry_conflict(
        IndividualSignup.objects.get(pk=stray.pk)
    )
    with pytest.raises(reg.RegistrationError, match="名单中"):
        reg.form_teams(
            tournament=tournament, actor=_admin(), layout=_layout(("一队", entries))
        )


@pytest.mark.django_db
def test_a_member_who_no_longer_qualifies_is_refused():
    tournament = _tournament()
    entries = _pool(tournament, 2)
    ContactMethod.objects.filter(user=entries[1].user).delete()

    with pytest.raises(reg.RegistrationError, match="资料不完整"):
        reg.form_teams(
            tournament=tournament, actor=_admin(), layout=_layout(("一队", entries))
        )


@pytest.mark.django_db
def test_below_the_minimum_saves(django_capture_on_commit_callbacks):
    tournament = _tournament(roster_min=3, roster_max=5)
    entries = _pool(tournament, 2)

    reg.form_teams(
        tournament=tournament, actor=_admin(), layout=_layout(("小队", entries))
    )

    assert tournament.registrations.get().status == APPROVED


# --- adjusting, returning, dissolving ------------------------------------------------


@pytest.mark.django_db
def test_moving_a_member_between_teams(django_capture_on_commit_callbacks):
    tournament = _tournament()
    entries = _pool(tournament, 4)
    admin = _admin()
    reg.form_teams(
        tournament=tournament,
        actor=admin,
        layout=_layout(("一队", entries[:2]), ("二队", entries[2:])),
    )
    one = tournament.registrations.get(team_name="一队")
    two = tournament.registrations.get(team_name="二队")
    mail.outbox.clear()

    with django_capture_on_commit_callbacks(execute=True):
        result = reg.form_teams(
            tournament=tournament,
            actor=admin,
            layout=[
                _existing(one, "一队", entries[:1]),
                _existing(two, "二队", entries[1:]),
            ],
        )

    assert result["updated"] == 2 and result["returned"] == 1
    assert {row.user for row in one.members.all()} == {entries[0].user}
    assert {row.user for row in two.members.all()} == {e.user for e in entries[1:]}
    one.refresh_from_db()
    two.refresh_from_db()
    assert (one.roster_version, two.roster_version) == (2, 2)
    assert one.logs.order_by("-id").first().action == RegistrationAction.SYNC_ROSTER
    moved = IndividualSignup.objects.get(pk=entries[1].pk)
    assert moved.registration == two
    subjects = sorted((m.to[0], m.subject) for m in mail.outbox)
    assert subjects == [
        (entries[1].user.email, "临时队伍有变化"),
        (entries[1].user.email, "已编入临时队伍"),
    ]


@pytest.mark.django_db
def test_renaming_keeps_members_and_logs_the_change():
    tournament = _tournament()
    entries = _pool(tournament, 2)
    admin = _admin()
    reg.form_teams(
        tournament=tournament, actor=admin, layout=_layout(("一队", entries))
    )
    registration = tournament.registrations.get()

    reg.form_teams(
        tournament=tournament,
        actor=admin,
        layout=[_existing(registration, "壹队", entries)],
    )

    registration.refresh_from_db()
    assert registration.team_name == "壹队"
    assert registration.members.count() == 2
    assert registration.logs.count() == 2


@pytest.mark.django_db
def test_saving_the_same_layout_changes_nothing():
    tournament = _tournament()
    entries = _pool(tournament, 2)
    admin = _admin()
    reg.form_teams(
        tournament=tournament, actor=admin, layout=_layout(("一队", entries))
    )
    registration = tournament.registrations.get()

    result = reg.form_teams(
        tournament=tournament,
        actor=admin,
        layout=[_existing(registration, "一队", entries)],
    )

    assert result == {"created": 0, "updated": 0, "dissolved": 0, "returned": 0}
    assert registration.logs.count() == 1


@pytest.mark.django_db
def test_emptying_a_team_on_the_board_dissolves_it(django_capture_on_commit_callbacks):
    tournament = _tournament()
    entries = _pool(tournament, 2)
    admin = _admin()
    reg.form_teams(
        tournament=tournament, actor=admin, layout=_layout(("一队", entries))
    )
    registration = tournament.registrations.get()
    mail.outbox.clear()

    with django_capture_on_commit_callbacks(execute=True):
        result = reg.form_teams(
            tournament=tournament,
            actor=admin,
            layout=[_existing(registration, "一队", [])],
        )

    assert result["dissolved"] == 1 and result["returned"] == 2
    registration.refresh_from_db()
    assert registration.status == WITHDRAWN
    assert not registration.members.filter(is_active=True).exists()
    assert not IndividualSignup.objects.filter(registration__isnull=False).exists()
    assert (
        registration.logs.order_by("-id").first().action == RegistrationAction.DISSOLVE
    )
    assert {m.subject for m in mail.outbox} == {"临时队伍有变化"}


@pytest.mark.django_db
def test_dissolving_returns_everyone_and_mails_them(django_capture_on_commit_callbacks):
    tournament = _tournament()
    entries = _pool(tournament, 2)
    admin = _admin()
    reg.form_teams(
        tournament=tournament, actor=admin, layout=_layout(("一队", entries))
    )
    registration = tournament.registrations.get()
    mail.outbox.clear()

    with django_capture_on_commit_callbacks(execute=True):
        reg.dissolve(registration=registration, actor=admin)

    registration.refresh_from_db()
    assert registration.status == WITHDRAWN
    assert not IndividualSignup.objects.filter(registration__isnull=False).exists()
    assert len(mail.outbox) == 2
    assert all("已由赛事管理员解散" in m.body for m in mail.outbox)
    with pytest.raises(reg.RegistrationError, match="不在报名中"):
        reg.dissolve(registration=registration, actor=admin)


@pytest.mark.django_db
def test_a_team_registration_cannot_be_dissolved_or_left():
    tournament = _tournament()
    captain = player("real-cap@example.com", "真队长")
    mate = player("real-mate@example.com", "真队友")
    team = team_services.create_team(user=captain, name="真战队")
    application = team_services.apply_to_team(
        team=team, user=mate, roles={"tank": True}
    )
    team_services.approve_application(application=application, actor=captain)
    registration = reg.submit(
        tournament=tournament,
        team=team,
        actor=captain,
        selections={
            str(m.user.pk): m.user.game_accounts.first().pk
            for m in team.memberships.all()
        },
    )

    with pytest.raises(reg.RegistrationError, match="只有临时队伍"):
        reg.dissolve(registration=registration, actor=_admin())
    with pytest.raises(reg.RegistrationError, match="队长撤回"):
        reg.leave(registration=registration, user=mate)


# --- leaving --------------------------------------------------------------------------


@pytest.fixture
def formed(db):
    call_command("init_site", verbosity=0)
    tournament = _tournament()
    entries = _pool(tournament, 3)
    admin = _admin()
    admin.groups.add(Group.objects.get(name="赛事管理员"))
    reg.form_teams(
        tournament=tournament, actor=admin, layout=_layout(("一队", entries))
    )
    return tournament, tournament.registrations.get(), entries, admin


@pytest.mark.django_db
def test_a_member_leaves_before_the_deadline(
    formed, django_capture_on_commit_callbacks
):
    tournament, registration, entries, admin = formed
    leaver = entries[0]
    mail.outbox.clear()

    with django_capture_on_commit_callbacks(execute=True):
        dissolved = reg.leave(registration=registration, user=leaver.user)

    assert dissolved is False
    assert not registration.members.filter(user=leaver.user).exists()
    assert registration.members.count() == 2
    assert IndividualSignup.objects.get(pk=leaver.pk).registration is None
    registration.refresh_from_db()
    assert registration.status == APPROVED
    assert registration.roster_version == 2
    log = registration.logs.order_by("-id").first()
    assert (log.action, log.actor_type, log.actor_user) == (
        RegistrationAction.MEMBER_LEFT,
        ActorType.MEMBER,
        leaver.user,
    )
    # Design 10.2: the tournament admins hear, the member does not get a copy.
    assert [m.subject for m in mail.outbox] == ["临时队伍成员退出"]
    assert mail.outbox[0].to == [admin.email]
    assert leaver.user.nickname in mail.outbox[0].body


@pytest.mark.django_db
def test_leaving_after_the_deadline_is_refused(formed):
    tournament, registration, entries, _admin_user = formed
    Tournament.objects.filter(pk=tournament.pk).update(
        registration_closes_at=timezone.now() - timedelta(hours=1)
    )
    registration.refresh_from_db()

    with pytest.raises(reg.RegistrationError, match="报名已截止"):
        reg.leave(registration=registration, user=entries[0].user)
    assert registration.members.count() == 3


@pytest.mark.django_db
def test_a_stranger_cannot_leave(formed):
    _tournament_, registration, _entries, _admin_user = formed
    stranger = player("stranger-leave@example.com", "路人")

    with pytest.raises(reg.RegistrationError, match="不在这支队伍"):
        reg.leave(registration=registration, user=stranger)


@pytest.mark.django_db
def test_the_last_member_leaving_dissolves_the_team(
    formed, django_capture_on_commit_callbacks
):
    tournament, registration, entries, _admin_user = formed
    for entry in entries[:2]:
        reg.leave(registration=registration, user=entry.user)
    mail.outbox.clear()

    with django_capture_on_commit_callbacks(execute=True):
        dissolved = reg.leave(registration=registration, user=entries[2].user)

    assert dissolved is True
    registration.refresh_from_db()
    assert registration.status == WITHDRAWN
    log = registration.logs.order_by("-id").first()
    assert (log.action, log.actor_type) == (
        RegistrationAction.DISSOLVE,
        ActorType.SYSTEM,
    )
    assert log.note == reg.AUTO_DISSOLVE_NOTE
    assert "已自动解散" in mail.outbox[0].body


@pytest.mark.django_db
def test_a_returned_member_can_be_placed_again(formed):
    tournament, registration, entries, admin = formed
    reg.leave(registration=registration, user=entries[0].user)

    reg.form_teams(
        tournament=tournament,
        actor=admin,
        layout=[_existing(registration, "一队", entries)],
    )

    assert registration.members.filter(user=entries[0].user, is_active=True).exists()


@pytest.mark.django_db
def test_withdraw_is_refused_for_an_adhoc_team(formed):
    _tournament_, registration, entries, _admin_user = formed
    with pytest.raises(reg.RegistrationError, match="临时队伍由管理员解散"):
        reg.withdraw(registration=registration, actor=entries[0].user)


# --- the front end --------------------------------------------------------------------


@pytest.mark.django_db
def test_the_detail_page_offers_leaving_to_members_only(client, formed):
    _tournament_, registration, entries, _admin_user = formed
    url = registration.get_absolute_url()
    leave_url = reverse("registration_leave", args=[registration.pk])

    client.force_login(entries[0].user)
    html = client.get(url).content.decode()
    assert "临时队伍" in html
    assert leave_url in html
    assert re.search(r'href="/teams/\d+/"', html) is None
    assert "撤回报名" not in html

    stranger = player("stranger-page@example.com", "路人")
    client.force_login(stranger)
    assert client.get(url).status_code == 404


@pytest.mark.django_db
def test_leaving_through_the_page(client, formed):
    tournament, registration, entries, _admin_user = formed
    client.force_login(entries[0].user)

    response = client.post(reverse("registration_leave", args=[registration.pk]))

    assert response.status_code == 302
    assert response.url == tournament.get_absolute_url()
    assert not registration.members.filter(user=entries[0].user).exists()


@pytest.mark.django_db
def test_the_slot_and_my_registrations_show_the_team(client, formed):
    tournament, registration, entries, _admin_user = formed
    client.force_login(entries[0].user)

    fragment = client.get(
        reverse("state_fragment") + f"?slots=tournament-actions:{tournament.pk}"
    ).content.decode()
    mine = client.get(reverse("me_registrations")).content.decode()

    assert "已编入「一队」" in fragment
    assert registration.get_absolute_url() in fragment
    assert "已编入「一队」" in mine


# --- the board (design 14.2) ----------------------------------------------------------


@pytest.fixture
def board(client, db):
    call_command("init_site", verbosity=0)

    def render(tournament, user=None):
        if user is None:
            user = _admin()
            user.is_staff = True
            user.save()
            user.groups.add(Group.objects.get(name="赛事管理员"))
        client.force_login(user)
        response = client.get(f"/admin/tournaments/{tournament.pk}/teams/")
        return response

    return render


@pytest.mark.django_db
def test_a_tournament_manager_opens_the_board_and_an_editor_does_not(board):
    tournament = _tournament()
    _pool(tournament, 2)

    assert board(tournament).status_code == 200

    editor = player("editor-board@example.com", "内容编辑甲")
    editor.groups.add(Group.objects.get(name="内容编辑"))
    response = board(tournament, user=editor)
    assert response.status_code in (302, 403)


@pytest.mark.django_db
def test_the_board_carries_what_the_script_and_the_view_need(board):
    tournament = _tournament(roster_min=2, roster_max=3)
    entries = _pool(tournament, 3)
    admin = _admin()
    reg.form_teams(
        tournament=tournament, actor=admin, layout=_layout(("一队", entries[:2]))
    )
    registration = tournament.registrations.get()

    html = board(tournament).content.decode()

    assert 'data-zone-team=""' in html  # the pool
    assert f'data-zone-team="r{registration.pk}"' in html
    assert 'data-zone-team="new"' in html
    assert 'data-zone-capacity="3"' in html
    assert 'data-zone-min="2"' in html
    for entry in entries:
        assert f'name="team-{entry.pk}"' in html
    assert f'name="name-r{registration.pk}"' in html
    assert 'name="name-new"' in html
    assert "Sortable.min.js" in html and "tournament-teams.js" in html
    assert "cdn" not in html.lower()
    for attribute in ("x-data", "x-on:", "x-ref", "@click", "onclick=", "style="):
        assert attribute not in html, attribute
    assert "未填段位" in html  # the pool entries have no tank rank


@pytest.mark.django_db
def test_saving_from_the_board_posts_the_same_fields_the_view_reads(client, board):
    tournament = _tournament()
    entries = _pool(tournament, 3)
    admin = _admin()
    reg.form_teams(
        tournament=tournament, actor=admin, layout=_layout(("一队", entries[:1]))
    )
    registration = tournament.registrations.get()
    board(tournament)  # logs a manager in

    payload = {
        "action": "save",
        f"name-r{registration.pk}": "一队",
        "name-new": "二队",
        f"team-{entries[0].pk}": f"r{registration.pk}",
        f"team-{entries[1].pk}": f"r{registration.pk}",
        f"team-{entries[2].pk}": "new",
    }
    response = client.post(f"/admin/tournaments/{tournament.pk}/teams/", payload)

    assert response.status_code == 302
    assert tournament.registrations.filter(status=APPROVED).count() == 2
    two = tournament.registrations.get(team_name="二队")
    assert [row.user for row in two.members.all()] == [entries[2].user]
    assert registration.members.count() == 2


@pytest.mark.django_db
def test_a_refused_layout_shows_the_problems_and_changes_nothing(client, board):
    tournament = _tournament(roster_max=2)
    entries = _pool(tournament, 3)
    board(tournament)

    payload = {"action": "save", "name-new": "超员"}
    for entry in entries:
        payload[f"team-{entry.pk}"] = "new"
    response = client.post(
        f"/admin/tournaments/{tournament.pk}/teams/", payload, follow=True
    )

    assert "超过上限" in response.content.decode()
    assert not tournament.registrations.exists()


@pytest.mark.django_db
def test_dissolving_from_the_board(client, board):
    tournament = _tournament()
    entries = _pool(tournament, 2)
    reg.form_teams(
        tournament=tournament, actor=_admin(), layout=_layout(("一队", entries))
    )
    registration = tournament.registrations.get()
    board(tournament)

    response = client.post(
        f"/admin/tournaments/{tournament.pk}/teams/",
        {"action": "dissolve", "registration": registration.pk},
    )

    assert response.status_code == 302
    registration.refresh_from_db()
    assert registration.status == WITHDRAWN


@pytest.mark.django_db
def test_the_review_page_shows_an_adhoc_team_read_only(client, board):
    tournament = _tournament()
    entries = _pool(tournament, 2)
    reg.form_teams(
        tournament=tournament, actor=_admin(), layout=_layout(("一队", entries))
    )
    registration = tournament.registrations.get()
    board(tournament)

    html = client.get(
        reverse("registration_review_detail", args=[registration.pk])
    ).content.decode()

    assert "临时队伍" in html
    assert "在队伍编排页管理" in html
    assert 'value="revoke"' not in html
    assert 'value="approve"' not in html


# --- cancellation, deletion, regeneration ---------------------------------------------


@pytest.mark.django_db
def test_cancelling_the_tournament_mails_adhoc_members(
    formed, django_capture_on_commit_callbacks
):
    from tournaments import services

    tournament, _registration, entries, admin = formed
    mail.outbox.clear()

    with django_capture_on_commit_callbacks(execute=True):
        services.cancel(tournament=tournament, actor=admin, reason="场地没了")

    assert sorted(m.to[0] for m in mail.outbox if m.subject == "赛事已取消") == sorted(
        e.user.email for e in entries
    )


@pytest.mark.django_db
def test_deleting_a_placed_account_frees_the_place(formed):
    from accounts.services import delete_account

    tournament, registration, entries, _admin_user = formed
    Tournament.objects.filter(pk=tournament.pk).update(
        registration_closes_at=timezone.now() - timedelta(hours=1)
    )

    delete_account(entries[0].user)

    assert not registration.members.filter(user=entries[0].user).exists()
    assert registration.members.count() == 2
    assert not IndividualSignup.objects.filter(user=entries[0].user).exists()


@pytest.mark.django_db
def test_forming_and_leaving_refresh_the_tournament_page(prerender_on, formed):
    tournament, registration, entries, _admin_user = formed
    PrerenderedPage.objects.all().delete()

    reg.leave(registration=registration, user=entries[0].user)

    assert PrerenderedPage.objects.filter(path=tournament.get_absolute_url()).exists()


@pytest.mark.django_db
def test_two_adhoc_teams_coexist_in_one_tournament():
    tournament = _tournament()
    entries = _pool(tournament, 4)

    reg.form_teams(
        tournament=tournament,
        actor=_admin(),
        layout=_layout(("一队", entries[:2]), ("二队", entries[2:])),
    )

    assert (
        Registration.objects.filter(tournament=tournament, team__isnull=True).count()
        == 2
    )


@pytest.mark.django_db
def test_the_export_names_the_team_for_a_placed_entry(formed):
    from accounts.services import personal_data

    _tournament_, _registration, entries, _admin_user = formed

    data = personal_data(entries[0].user)

    assert data["individual_signups"][0]["team"] == "一队"
