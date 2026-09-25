import csv
import io
from datetime import timedelta

import pytest
from django.contrib.auth.models import Group
from django.core.management import call_command
from django.urls import reverse
from django.utils import timezone

from accounts.models import ContactMethod, ContactType, GameAccount, User
from teams import services as team_services
from tournaments import registration as reg
from tournaments.models import RegistrationStatus, Tournament, TournamentStatus


def _player(email, nickname):
    user = User.objects.create_user(
        email=email,
        password="Correct-Horse-Battery-1",
        nickname=nickname,
        is_sjtu=True,
        agreed_terms_at=timezone.now(),
        agreed_cross_border_at=timezone.now(),
    )
    GameAccount.objects.create(user=user, battletag=f"{nickname}#1234")
    ContactMethod.objects.create(user=user, type=ContactType.QQ, value="123456789")
    return user


@pytest.fixture
def site(db):
    call_command("init_site", verbosity=0)


@pytest.fixture
def manager(site):
    user = _player("review-manager@example.com", "审核管理员")
    user.is_staff = True
    user.save()
    user.groups.add(Group.objects.get(name="赛事管理员"))
    return user


@pytest.fixture
def registration(site):
    captain = _player("review-cap@example.com", "审核队长")
    mate = _player("review-mate@example.com", "审核队员")
    team = team_services.create_team(user=captain, name="审核战队")
    application = team_services.apply_to_team(
        team=team, user=mate, roles={"tank": True}
    )
    team_services.approve_application(application=application, actor=captain)
    now = timezone.now()
    tournament = Tournament.objects.create(
        title="审核赛",
        registration_opens_at=now - timedelta(days=1),
        registration_closes_at=now + timedelta(days=7),
        roster_min=2,
        roster_max=3,
        status=TournamentStatus.PUBLISHED,
        published_at=now,
    )
    selections = {
        str(membership.user.pk): membership.user.game_accounts.first().pk
        for membership in team.memberships.all()
    }
    return reg.submit(
        tournament=tournament, team=team, actor=captain, selections=selections
    )


@pytest.mark.django_db
def test_only_tournament_managers_get_in(client, registration, manager):
    plain = _player("review-plain@example.com", "路人")
    client.force_login(plain)
    assert client.get(reverse("registration_review_index")).status_code == 302

    client.force_login(manager)
    response = client.get(reverse("registration_review_index"))
    assert response.status_code == 200
    assert "审核战队" in response.content.decode()


@pytest.mark.django_db
def test_list_defaults_to_pending_and_filters(client, registration, manager):
    client.force_login(manager)
    reg.approve(registration=registration, actor=manager)

    default = client.get(reverse("registration_review_index")).content.decode()
    assert "审核战队" not in default  # approved, so not in the pending default

    approved = client.get(
        reverse("registration_review_index") + "?status=approved"
    ).content.decode()
    assert "审核战队" in approved

    other = client.get(
        reverse("registration_review_index")
        + f"?status=approved&tournament={registration.tournament_id + 99}"
    ).content.decode()
    assert "审核战队" not in other


@pytest.mark.django_db
def test_detail_shows_roster_diff_and_logs(client, registration, manager):
    client.force_login(manager)
    third = _player("review-third@example.com", "后加入的")
    application = team_services.apply_to_team(
        team=registration.team, user=third, roles={"damage": True}
    )
    team_services.approve_application(
        application=application, actor=registration.team.captain()
    )
    html = client.get(
        reverse("registration_review_detail", args=[registration.pk])
    ).content.decode()
    assert "审核队长" in html
    assert "战队新增了 后加入的" in html
    assert "提交报名" in html


@pytest.mark.django_db
def test_contacts_need_the_permission(client, registration, manager, site):
    client.force_login(manager)  # 赛事管理员 has accounts.view_contactmethod
    html = client.get(
        reverse("registration_review_detail", args=[registration.pk])
    ).content.decode()
    assert "QQ 123456789" in html

    editor = _player("review-editor@example.com", "内容编辑")
    editor.is_staff = True
    editor.save()
    editor.groups.add(Group.objects.get(name="内容编辑"))
    client.force_login(editor)
    # Content editors cannot manage tournaments at all.
    assert client.get(
        reverse("registration_review_detail", args=[registration.pk]), follow=True
    ).redirect_chain


@pytest.mark.django_db
def test_actions_follow_the_status(client, registration, manager):
    """Design 8.7: the buttons follow the status and nothing else (round 067)."""
    client.force_login(manager)
    url = reverse("registration_review_detail", args=[registration.pk])
    html = client.get(url).content.decode()
    assert 'value="approve"' in html
    assert 'value="revoke"' not in html

    reg.approve(registration=registration, actor=manager)
    html = client.get(url).content.decode()
    assert 'value="revoke"' in html
    assert 'value="approve"' not in html

    reg.reject(registration=registration, actor=manager, note="不符合")
    html = client.get(url).content.decode()
    assert "没有可用的审核操作" in html


@pytest.mark.django_db
def test_approve_and_reject_from_the_admin(client, registration, manager):
    client.force_login(manager)
    url = reverse("registration_review_action", args=[registration.pk])
    client.post(url, {"action": "approve"}, follow=True)
    registration.refresh_from_db()
    assert registration.status == RegistrationStatus.APPROVED

    response = client.post(url, {"action": "revoke", "note": ""}, follow=True)
    registration.refresh_from_db()
    assert registration.status == RegistrationStatus.APPROVED  # note is required
    assert "备注" in response.content.decode()

    client.post(url, {"action": "revoke", "note": "名单有问题"}, follow=True)
    registration.refresh_from_db()
    assert registration.status == RegistrationStatus.REJECTED
    assert registration.status_note == "名单有问题"


@pytest.mark.django_db
def test_bulk_approve_reports_failures(client, registration, manager):
    client.force_login(manager)
    reg.withdraw(registration=registration, actor=registration.team.captain())
    response = client.post(
        reverse("registration_review_bulk"),
        {"registration": [registration.pk]},
        follow=True,
    )
    registration.refresh_from_db()
    assert registration.status == RegistrationStatus.WITHDRAWN
    assert "当前状态不能通过" in response.content.decode()


@pytest.mark.django_db
def test_bulk_approve_approves_the_rest(client, registration, manager):
    client.force_login(manager)
    client.post(
        reverse("registration_review_bulk"),
        {"registration": [registration.pk]},
        follow=True,
    )
    registration.refresh_from_db()
    assert registration.status == RegistrationStatus.APPROVED


@pytest.mark.django_db
def test_csv_export(client, registration, manager):
    client.force_login(manager)
    response = client.get(reverse("registration_review_export") + "?status=pending")
    assert response.status_code == 200
    assert response["Content-Type"].startswith("text/csv")
    body = response.content.decode("utf-8-sig")
    rows = list(csv.reader(io.StringIO(body)))
    assert rows[0][:3] == ["赛事", "战队", "状态"]
    assert "联系方式" in rows[0]
    assert any("审核队长" in row for row in rows[1:])
    assert any("QQ 123456789" in "".join(row) for row in rows[1:])


@pytest.mark.django_db
def test_export_is_logged(client, registration, manager):
    from wagtail.models import ModelLogEntry

    client.force_login(manager)
    before = ModelLogEntry.objects.count()
    # Even an unfiltered export leaves a trace on each tournament involved.
    client.get(reverse("registration_review_export"))
    assert ModelLogEntry.objects.count() > before
    entry = ModelLogEntry.objects.order_by("-pk").first()
    assert entry.user_id == manager.pk
    assert entry.object_id == str(registration.tournament_id)
    assert "含联系方式" in entry.data["detail"]
