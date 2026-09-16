from datetime import timedelta

import pytest
from django.contrib.auth.models import Group
from django.core.management import call_command
from django.urls import reverse
from django.utils import timezone

from accounts.models import User
from core.models import SiteSettings
from teams import services as team_services
from tournaments import services
from tournaments.models import ReviewMode, Tournament, TournamentStatus


def _user(email, nickname, **flags):
    return User.objects.create_user(
        email=email,
        password="Correct-Horse-Battery-1",
        nickname=nickname,
        agreed_terms_at=timezone.now(),
        agreed_cross_border_at=timezone.now(),
        **flags,
    )


@pytest.fixture
def manager(db):
    call_command("init_site", verbosity=0)
    user = _user("manager@example.com", "赛事管理员甲")
    user.is_staff = True
    user.save()
    user.groups.add(Group.objects.get(name="赛事管理员"))
    return user


def _tournament(**kwargs):
    now = timezone.now()
    kwargs.setdefault("title", "春季赛")
    kwargs.setdefault("summary", "校内赛事")
    kwargs.setdefault("registration_opens_at", now - timedelta(days=1))
    kwargs.setdefault("registration_closes_at", now + timedelta(days=7))
    kwargs.setdefault("roster_min", 5)
    kwargs.setdefault("roster_max", 6)
    kwargs.setdefault("status", TournamentStatus.PUBLISHED)
    kwargs.setdefault("published_at", now)
    return Tournament.objects.create(**kwargs)


# --- model ---------------------------------------------------------------------


@pytest.mark.django_db
def test_roster_range_is_enforced_by_the_database():
    from django.db.utils import IntegrityError

    with pytest.raises(IntegrityError):
        _tournament(roster_min=7, roster_max=6)


@pytest.mark.django_db
def test_registration_window_is_enforced_by_the_database():
    from django.db.utils import IntegrityError

    now = timezone.now()
    with pytest.raises(IntegrityError):
        _tournament(
            registration_opens_at=now + timedelta(days=2),
            registration_closes_at=now + timedelta(days=1),
        )


@pytest.mark.django_db
def test_external_id_is_unique_when_set():
    from django.db.utils import IntegrityError

    _tournament(external_id="up-1")
    _tournament(title="第二个", external_id="")
    _tournament(title="第三个", external_id="")  # blanks do not collide
    with pytest.raises(IntegrityError):
        _tournament(title="重复", external_id="up-1")


@pytest.mark.django_db
def test_phases():
    now = timezone.now()
    upcoming = _tournament(
        title="还没开始",
        registration_opens_at=now + timedelta(days=1),
        registration_closes_at=now + timedelta(days=3),
    )
    closed = _tournament(
        title="已截止",
        registration_opens_at=now - timedelta(days=5),
        registration_closes_at=now - timedelta(days=1),
    )
    open_now = _tournament(title="报名中")
    finished = _tournament(title="打完了", status=TournamentStatus.FINISHED)
    assert upcoming.phase() == "upcoming"
    assert closed.phase() == "closed"
    assert open_now.phase() == "open"
    assert finished.phase() == "finished"
    assert open_now.registration_open() is True
    assert closed.registration_open() is False


# --- pages ---------------------------------------------------------------------


@pytest.mark.django_db
def test_list_groups_and_hides_drafts_and_cancelled(client):
    _tournament(title="报名中的")
    _tournament(title="草稿的", status=TournamentStatus.DRAFT, published_at=None)
    _tournament(title="取消的", status=TournamentStatus.CANCELLED)
    html = client.get(reverse("tournament_index")).content.decode()
    assert "报名中的" in html
    assert "草稿的" not in html
    assert "取消的" not in html
    assert "报名中" in html  # the group heading


@pytest.mark.django_db
def test_draft_detail_is_404_but_cancelled_is_visible(client):
    draft = _tournament(status=TournamentStatus.DRAFT, published_at=None)
    cancelled = _tournament(title="取消的", status=TournamentStatus.CANCELLED)
    assert client.get(reverse("tournament_detail", args=[draft.pk])).status_code == 404
    response = client.get(reverse("tournament_detail", args=[cancelled.pk]))
    assert response.status_code == 200
    assert "已取消" in response.content.decode()


@pytest.mark.django_db
def test_actions_slot_for_each_kind_of_visitor(client):
    tournament = _tournament()
    url = reverse("state_fragment") + f"?slots=tournament-actions:{tournament.pk}"

    anonymous = client.get(url).content.decode()
    assert "登录后报名" in anonymous

    plain = _user("plain@example.com", "普通用户")
    client.force_login(plain)
    assert "需要由队长为战队报名" in client.get(url).content.decode()

    captain = _user("captain-t@example.com", "队长丙")
    team_services.create_team(user=captain, name="报名队")
    client.force_login(captain)
    html = client.get(url).content.decode()
    assert "报名队" in html
    assert "即将开放" in html


@pytest.mark.django_db
def test_closed_registration_says_so(client):
    now = timezone.now()
    tournament = _tournament(
        registration_opens_at=now - timedelta(days=5),
        registration_closes_at=now - timedelta(days=1),
    )
    captain = _user("captain-closed@example.com", "队长丁")
    team_services.create_team(user=captain, name="来晚了")
    client.force_login(captain)
    url = reverse("state_fragment") + f"?slots=tournament-actions:{tournament.pk}"
    assert "不在报名时间内" in client.get(url).content.decode()


@pytest.mark.django_db
def test_sitemap_lists_published_tournaments_only(client):
    listed = _tournament(title="进 sitemap 的")
    cancelled = _tournament(title="取消的", status=TournamentStatus.CANCELLED)
    xml = client.get("/sitemap.xml").content.decode()
    assert listed.get_absolute_url() in xml
    assert cancelled.get_absolute_url() not in xml


# --- services ------------------------------------------------------------------


@pytest.mark.django_db
def test_publish_finish_cancel(manager):
    tournament = _tournament(status=TournamentStatus.DRAFT, published_at=None)
    services.publish(tournament=tournament, actor=manager)
    tournament.refresh_from_db()
    assert tournament.status == TournamentStatus.PUBLISHED
    assert tournament.published_at is not None

    services.finish(tournament=tournament, actor=manager)
    tournament.refresh_from_db()
    assert tournament.status == TournamentStatus.FINISHED

    with pytest.raises(services.TournamentError):
        services.finish(tournament=tournament, actor=manager)

    services.cancel(tournament=tournament, actor=manager, reason="场地问题")
    tournament.refresh_from_db()
    assert tournament.status == TournamentStatus.CANCELLED
    with pytest.raises(services.TournamentError):
        services.cancel(tournament=tournament, actor=manager)


@pytest.mark.django_db
def test_published_tournaments_cannot_be_deleted(manager):
    draft = _tournament(status=TournamentStatus.DRAFT, published_at=None)
    assert services.can_delete(draft) is True
    services.publish(tournament=draft, actor=manager)
    draft.refresh_from_db()
    assert services.can_delete(draft) is False


@pytest.mark.django_db
def test_roster_min_warning(manager):
    site = SiteSettings.load()
    site.team_max_members = 6
    site.save()
    assert services.roster_min_warning(_tournament(roster_min=5)) == ""
    warning = services.roster_min_warning(
        _tournament(title="人多", roster_min=7, roster_max=8)
    )
    assert "没有战队能满足" in warning


@pytest.mark.django_db
def test_changes_queue_prerender_and_moderation(manager, settings, tmp_path):
    from core.models import PrerenderedPage
    from moderation.models import ModerationItem

    settings.PRERENDER_ENABLED = True
    settings.PRERENDER_ROOT = tmp_path
    settings.MODERATION_API_KEY = "test-key"
    tournament = _tournament(description="欢迎报名，详情见群公告。")
    services.after_change(tournament, actor=manager)
    paths = set(PrerenderedPage.objects.values_list("path", flat=True))
    assert {tournament.get_absolute_url(), "/tournaments/"} <= paths
    assert ModerationItem.objects.filter(target_type="tournament_description").exists()


@pytest.mark.django_db
def test_cancelling_removes_the_static_page(manager, settings, tmp_path):
    from core.models import PrerenderedPage

    settings.PRERENDER_ENABLED = True
    settings.PRERENDER_ROOT = tmp_path
    tournament = _tournament()
    services.after_change(tournament, actor=manager)
    assert PrerenderedPage.objects.filter(path=tournament.get_absolute_url()).exists()
    services.cancel(tournament=tournament, actor=manager)
    # The removal task is queued; the record is dropped when it runs.
    assert tournament.is_listed is False


# --- admin ---------------------------------------------------------------------


@pytest.mark.django_db
def test_admin_needs_the_permission(client, manager):
    plain = _user("nostaff@example.com", "路人戊")
    client.force_login(plain)
    # No admin access at all: Wagtail bounces to the login page.
    assert client.get("/admin/tournaments/").status_code == 302

    client.force_login(manager)
    response = client.get("/admin/tournaments/")
    assert response.status_code == 200


@pytest.mark.django_db
def test_manager_can_publish_from_the_admin(client, manager):
    tournament = _tournament(status=TournamentStatus.DRAFT, published_at=None)
    client.force_login(manager)
    url = reverse("tournament_action", args=[tournament.pk, "publish"])
    assert client.get(url).status_code == 200
    client.post(url, follow=True)
    tournament.refresh_from_db()
    assert tournament.status == TournamentStatus.PUBLISHED


@pytest.mark.django_db
def test_manager_can_cancel_with_a_reason(client, manager):
    tournament = _tournament()
    client.force_login(manager)
    url = reverse("tournament_cancel", args=[tournament.pk])
    assert client.get(url).status_code == 200
    client.post(url, {"reason": "场地问题"}, follow=True)
    tournament.refresh_from_db()
    assert tournament.status == TournamentStatus.CANCELLED


@pytest.mark.django_db
def test_review_mode_default_and_choices():
    tournament = _tournament()
    assert tournament.review_mode == ReviewMode.LOCAL
    assert services.has_registrations(tournament) is False


@pytest.mark.django_db
def test_content_editors_cannot_manage_tournaments(client, manager):
    editor = _user("editor-t@example.com", "内容编辑甲")
    editor.is_staff = True
    editor.save()
    editor.groups.add(Group.objects.get(name="内容编辑"))
    client.force_login(editor)

    # Can reach the admin, but not the tournament area.
    assert client.get(reverse("wagtailadmin_home")).status_code == 200
    assert client.get("/admin/tournaments/", follow=True).redirect_chain
    assert services.can_manage(editor) is False

    tournament = _tournament()
    action = reverse("tournament_action", args=[tournament.pk, "publish"])
    assert client.get(action, follow=True).redirect_chain
