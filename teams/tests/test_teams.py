import pytest
from django.core import mail
from django.urls import reverse
from django.utils import timezone

from accounts.models import Feature, FeatureUserRule, GameAccount, User
from core.models import SiteSettings
from teams import services
from teams.models import (
    ApplicationStatus,
    Team,
    TeamRole,
)


def _user(email, nickname, with_game_account=True):
    user = User.objects.create_user(
        email=email,
        password="Correct-Horse-Battery-1",
        nickname=nickname,
        agreed_terms_at=timezone.now(),
        agreed_cross_border_at=timezone.now(),
    )
    if with_game_account:
        GameAccount.objects.create(user=user, battletag=f"{nickname}#1234")
    return user


@pytest.fixture
def captain(db):
    return _user("captain@example.com", "队长甲")


@pytest.fixture
def applicant(db):
    return _user("applicant@example.com", "申请人乙")


@pytest.fixture
def team(captain):
    return services.create_team(user=captain, name="交大一队", description="欢迎加入")


# --- creating ------------------------------------------------------------------


@pytest.mark.django_db
def test_creator_becomes_captain(team, captain):
    assert team.captain() == captain
    assert team.memberships.get(user=captain).role == TeamRole.CAPTAIN
    assert team.is_recruiting is True


@pytest.mark.django_db
def test_names_are_unique_case_insensitively(captain, applicant):
    services.create_team(user=captain, name="SJTU Alpha")
    with pytest.raises(services.TeamError):
        services.create_team(user=applicant, name="sjtu alpha")


@pytest.mark.django_db
def test_a_disbanded_name_can_be_reused(team, captain, applicant):
    services.disband_team(team=team, actor=captain)
    reused = services.create_team(user=applicant, name="交大一队")
    assert reused.pk != team.pk


@pytest.mark.django_db
def test_captain_limit(captain):
    site = SiteSettings.load()
    site.team_max_captained = 2
    site.save()
    services.create_team(user=captain, name="一队")
    services.create_team(user=captain, name="二队")
    with pytest.raises(services.TeamError) as exc:
        services.create_team(user=captain, name="三队")
    assert "队长" in str(exc.value)


@pytest.mark.django_db
def test_team_create_can_be_blocked_per_user(captain):
    FeatureUserRule.objects.create(
        user=captain, feature=Feature.TEAM_CREATE, allowed=False
    )
    with pytest.raises(services.TeamError) as exc:
        services.create_team(user=captain, name="被禁用的队")
    assert "无法使用" in str(exc.value)


# --- applying ------------------------------------------------------------------


@pytest.mark.django_db
def test_application_conditions(team, applicant):
    allowed, reason = services.can_apply(team, applicant)
    assert allowed, reason

    member_only = _user("nogame@example.com", "没有游戏ID", with_game_account=False)
    allowed, reason = services.can_apply(team, member_only)
    assert not allowed and "游戏 ID" in reason

    team.is_recruiting = False
    team.save()
    allowed, reason = services.can_apply(team, applicant)
    assert not allowed and "招募" in reason


@pytest.mark.django_db
def test_full_team_cannot_be_applied_to(team, applicant):
    site = SiteSettings.load()
    site.team_max_members = 1
    site.save()
    allowed, reason = services.can_apply(team, applicant)
    assert not allowed and "已满" in reason


@pytest.mark.django_db
def test_one_pending_application_per_team(team, applicant):
    services.apply_to_team(team=team, user=applicant, roles={"tank": True})
    with pytest.raises(services.TeamError):
        services.apply_to_team(team=team, user=applicant, roles={"tank": True})


@pytest.mark.django_db
def test_applying_needs_a_role(team, applicant):
    with pytest.raises(services.TeamError) as exc:
        services.apply_to_team(team=team, user=applicant, roles={})
    assert "位置" in str(exc.value)


@pytest.mark.django_db
def test_application_mails_the_captain(team, applicant, captain):
    mail.outbox.clear()
    services.apply_to_team(
        team=team, user=applicant, roles={"support": True}, message="想加入"
    )
    assert len(mail.outbox) == 1
    assert captain.email in mail.outbox[0].recipients()


# --- approving -----------------------------------------------------------------


@pytest.mark.django_db
def test_approval_adds_the_member_and_mails_them(
    team, applicant, captain, django_capture_on_commit_callbacks
):
    application = services.apply_to_team(
        team=team, user=applicant, roles={"damage": True}
    )
    mail.outbox.clear()
    with django_capture_on_commit_callbacks(execute=True):
        services.approve_application(application=application, actor=captain)
    application.refresh_from_db()
    assert application.status == ApplicationStatus.APPROVED
    assert services.is_member(team, applicant)
    assert len(mail.outbox) == 1
    assert applicant.email in mail.outbox[0].recipients()


@pytest.mark.django_db
def test_approval_rechecks_the_size_limit(team, applicant, captain):
    application = services.apply_to_team(
        team=team, user=applicant, roles={"damage": True}
    )
    site = SiteSettings.load()
    site.team_max_members = 1  # someone else filled the team meanwhile
    site.save()
    with pytest.raises(services.TeamError) as exc:
        services.approve_application(application=application, actor=captain)
    assert "已满" in str(exc.value)
    assert not services.is_member(team, applicant)


@pytest.mark.django_db
def test_only_the_captain_can_approve(team, applicant):
    application = services.apply_to_team(
        team=team, user=applicant, roles={"damage": True}
    )
    outsider = _user("outsider@example.com", "路人丙")
    with pytest.raises(services.TeamError):
        services.approve_application(application=application, actor=outsider)


@pytest.mark.django_db
def test_rejection_keeps_the_door_open(team, applicant, captain):
    application = services.apply_to_team(
        team=team, user=applicant, roles={"damage": True}
    )
    services.reject_application(application=application, actor=captain, note="位置已满")
    application.refresh_from_db()
    assert application.status == ApplicationStatus.REJECTED
    assert application.decision_note == "位置已满"
    again = services.apply_to_team(team=team, user=applicant, roles={"tank": True})
    assert again.status == ApplicationStatus.PENDING


@pytest.mark.django_db
def test_applicant_can_cancel(team, applicant):
    application = services.apply_to_team(
        team=team, user=applicant, roles={"tank": True}
    )
    services.cancel_application(application=application, actor=applicant)
    application.refresh_from_db()
    assert application.status == ApplicationStatus.CANCELLED


# --- members -------------------------------------------------------------------


@pytest.mark.django_db
def test_captain_cannot_leave(team, captain):
    with pytest.raises(services.TeamError) as exc:
        services.leave_team(team=team, user=captain)
    assert "转让" in str(exc.value)


@pytest.mark.django_db
def test_member_can_leave(team, applicant, captain):
    application = services.apply_to_team(
        team=team, user=applicant, roles={"tank": True}
    )
    services.approve_application(application=application, actor=captain)
    services.leave_team(team=team, user=applicant)
    assert not services.is_member(team, applicant)


@pytest.mark.django_db
def test_captain_cannot_remove_themselves(team, captain):
    with pytest.raises(services.TeamError) as exc:
        services.remove_member(team=team, actor=captain, member_user=captain)
    assert "自己" in str(exc.value)


@pytest.mark.django_db
def test_removing_a_member_mails_them(team, applicant, captain):
    application = services.apply_to_team(
        team=team, user=applicant, roles={"tank": True}
    )
    services.approve_application(application=application, actor=captain)
    mail.outbox.clear()
    services.remove_member(team=team, actor=captain, member_user=applicant)
    assert not services.is_member(team, applicant)
    assert applicant.email in mail.outbox[0].recipients()


@pytest.mark.django_db
def test_transfer_swaps_the_roles(
    team, applicant, captain, django_capture_on_commit_callbacks
):
    application = services.apply_to_team(
        team=team, user=applicant, roles={"tank": True}
    )
    services.approve_application(application=application, actor=captain)
    mail.outbox.clear()
    with django_capture_on_commit_callbacks(execute=True):
        services.transfer_captain(team=team, actor=captain, new_captain=applicant)
    assert services.is_captain(team, applicant)
    assert not services.is_captain(team, captain)
    assert services.is_member(team, captain)
    assert applicant.email in mail.outbox[0].recipients()


@pytest.mark.django_db
def test_transfer_only_to_members(team, captain):
    outsider = _user("outsider2@example.com", "路人丁")
    with pytest.raises(services.TeamError) as exc:
        services.transfer_captain(team=team, actor=captain, new_captain=outsider)
    assert "现有成员" in str(exc.value)


@pytest.mark.django_db
def test_superuser_can_assign_a_captain(team, captain):
    admin = User.objects.create_superuser(
        email="admin-team@example.com",
        password="Correct-Horse-Battery-1",
        nickname="超管",
        agreed_terms_at=timezone.now(),
        agreed_cross_border_at=timezone.now(),
    )
    rescue = _user("rescue@example.com", "接手人")
    services.assign_captain(team=team, actor=admin, new_captain=rescue)
    assert services.is_captain(team, rescue)


# --- disbanding ----------------------------------------------------------------


@pytest.mark.django_db
def test_disband_clears_members_and_applications(
    team, applicant, captain, django_capture_on_commit_callbacks
):
    application = services.apply_to_team(
        team=team, user=applicant, roles={"tank": True}
    )
    mail.outbox.clear()
    with django_capture_on_commit_callbacks(execute=True):
        services.disband_team(team=team, actor=captain)
    team.refresh_from_db()
    application.refresh_from_db()
    assert team.is_disbanded
    assert team.memberships.count() == 0
    assert application.status == ApplicationStatus.CANCELLED
    assert captain.email in mail.outbox[0].recipients()


@pytest.mark.django_db
def test_only_captain_or_superuser_disbands(team, applicant):
    with pytest.raises(services.TeamError):
        services.disband_team(team=team, actor=applicant)


# --- pages ---------------------------------------------------------------------


@pytest.mark.django_db
def test_team_list_hides_disbanded_teams(client, team, captain):
    services.create_team(user=_user("c2@example.com", "队长戊"), name="交大二队")
    services.disband_team(team=team, actor=captain)
    html = client.get(reverse("team_index")).content.decode()
    assert "交大二队" in html
    assert "交大一队" not in html


@pytest.mark.django_db
def test_team_page_does_not_show_game_ids(client, team, applicant, captain):
    application = services.apply_to_team(
        team=team, user=applicant, roles={"tank": True}
    )
    services.approve_application(application=application, actor=captain)
    html = client.get(reverse("team_detail", args=[team.pk])).content.decode()
    assert applicant.nickname in html
    assert "申请人乙#1234" not in html  # game IDs stay on the manage page


@pytest.mark.django_db
def test_disbanded_team_page_says_so(client, team, captain):
    services.disband_team(team=team, actor=captain)
    html = client.get(reverse("team_detail", args=[team.pk])).content.decode()
    assert "已解散" in html


@pytest.mark.django_db
def test_anonymous_sees_a_login_prompt_in_the_join_slot(client, team):
    html = client.get(reverse("team_detail", args=[team.pk])).content.decode()
    assert "登录后申请" in html
    assert 'data-slot="team-join:' in html


@pytest.mark.django_db
def test_join_slot_fills_for_a_member(client, team, applicant, captain):
    application = services.apply_to_team(
        team=team, user=applicant, roles={"tank": True}
    )
    services.approve_application(application=application, actor=captain)
    client.force_login(applicant)
    url = reverse("state_fragment") + f"?slots=team-join:{team.pk}"
    html = client.get(url).content.decode()
    assert "你已是成员" in html
    assert 'hx-swap-oob="true"' in html


@pytest.mark.django_db
def test_manage_page_is_captain_only(client, team, applicant, captain):
    client.force_login(applicant)
    assert client.get(reverse("team_manage", args=[team.pk])).status_code == 404
    client.force_login(captain)
    assert client.get(reverse("team_manage", args=[team.pk])).status_code == 200


@pytest.mark.django_db
def test_manage_page_shows_game_ids(client, team, applicant, captain):
    services.apply_to_team(team=team, user=applicant, roles={"tank": True})
    client.force_login(captain)
    html = client.get(reverse("team_manage", args=[team.pk])).content.decode()
    assert "申请人乙#1234" in html


@pytest.mark.django_db
def test_me_teams_lists_membership_and_applications(client, team, applicant, captain):
    services.apply_to_team(team=team, user=applicant, roles={"tank": True})
    client.force_login(applicant)
    html = client.get(reverse("me_teams")).content.decode()
    assert "交大一队" in html
    assert "待审批" in html

    client.force_login(captain)
    html = client.get(reverse("me_teams")).content.decode()
    assert "队长" in html


@pytest.mark.django_db
def test_create_is_rate_limited(client, captain):
    client.force_login(captain)
    from django.core.cache import cache

    cache.clear()
    for index in range(services.max_captained()):
        response = client.post(
            reverse("team_create"),
            {"name": f"限流队{index}", "description": "", "is_recruiting": "on"},
            follow=True,
        )
        assert response.status_code == 200
    response = client.post(
        reverse("team_create"),
        {"name": "第四支", "description": "", "is_recruiting": "on"},
        follow=True,
    )
    assert Team.objects.filter(name="第四支").count() == 0


@pytest.mark.django_db
def test_team_changes_queue_moderation_and_prerender(team, settings, tmp_path):
    from moderation.models import ModerationItem

    settings.MODERATION_API_KEY = "test-key"
    settings.PRERENDER_ENABLED = True
    settings.PRERENDER_ROOT = tmp_path
    from core.models import PrerenderedPage

    services.update_team(
        team=team,
        user=team.captain(),
        name="改名后的队",
        description="新的简介",
        logo=None,
        is_recruiting=True,
    )
    types = set(ModerationItem.objects.values_list("target_type", flat=True))
    assert {"team_name", "team_description"} <= types
    paths = set(PrerenderedPage.objects.values_list("path", flat=True))
    assert {team.get_absolute_url(), "/teams/"} <= paths


@pytest.mark.django_db
def test_sitemap_lists_active_teams_only(client, team, captain):
    xml = client.get("/sitemap.xml").content.decode()
    assert f"/teams/{team.pk}/" in xml
    services.disband_team(team=team, actor=captain)
    xml = client.get("/sitemap.xml").content.decode()
    assert f"/teams/{team.pk}/" not in xml


# --- admin ---------------------------------------------------------------------


@pytest.fixture
def admin_user(db):
    return User.objects.create_superuser(
        email="superadmin-teams@example.com",
        password="Correct-Horse-Battery-1",
        nickname="超管队务",
        agreed_terms_at=timezone.now(),
        agreed_cross_border_at=timezone.now(),
    )


@pytest.mark.django_db
def test_team_admin_is_superuser_only(client, team, captain, admin_user):
    client.force_login(captain)
    assert client.get("/admin/teams/").status_code == 302

    client.force_login(admin_user)
    response = client.get("/admin/teams/")
    assert response.status_code == 200
    assert team.name in response.content.decode()


@pytest.mark.django_db
def test_admin_can_assign_a_captain(client, team, admin_user):
    rescue = _user("rescue-admin@example.com", "接手人乙")
    client.force_login(admin_user)
    url = reverse("team_assign_captain", args=[team.pk])
    assert client.get(url).status_code == 200
    client.post(url, {"user": rescue.pk}, follow=True)
    assert services.is_captain(team, rescue)


@pytest.mark.django_db
def test_admin_can_disband(client, team, admin_user):
    client.force_login(admin_user)
    client.post(reverse("team_admin_disband", args=[team.pk]), follow=True)
    team.refresh_from_db()
    assert team.is_disbanded


@pytest.mark.django_db
def test_duplicate_name_race_is_reported_not_crashed(captain, applicant, monkeypatch):
    services.create_team(user=captain, name="抢名字的队")
    # Pretend the pre-check passed and the insert hits the constraint.
    monkeypatch.setattr(services, "name_taken", lambda *args, **kwargs: False)
    with pytest.raises(services.TeamError) as exc:
        services.create_team(user=applicant, name="抢名字的队")
    assert "同名" in str(exc.value)


@pytest.mark.django_db
def test_team_list_does_not_run_a_query_per_team(
    django_assert_num_queries, client, captain
):
    for index in range(3):
        services.create_team(
            user=_user(f"cap{index}@example.com", f"队长{index}"), name=f"计数队{index}"
        )
    # 3 teams, still a constant number of queries (session, settings, list).
    with django_assert_num_queries(3):
        response = client.get(reverse("team_index"))
    assert response.status_code == 200
    assert "计数队0" in response.content.decode()
