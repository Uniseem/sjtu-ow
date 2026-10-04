"""Round 118: the admin functions the review found missing
(handoff/rounds/115-admin-review/findings.md #21, #24, #25, design 3.7).

The dashboard's 「待办」, the review queue's time filter, full scan and
handling history, the scrim split page's kept order, copy button and
contacts, and 「账号已停用」 wherever a roster or signup keeps such a person.
"""

import re
from datetime import timedelta
from pathlib import Path
from unittest import mock

import pytest
from allauth.account.models import EmailAddress
from django.conf import settings as django_settings
from django.contrib.auth.models import Group
from django.core.cache import cache
from django.core.management import call_command
from django.urls import reverse
from django.utils import timezone

from accounts.models import AvatarSubmission, ContactMethod, User
from accounts.services import GROUP_SUBMITTER
from core.models import PrerenderedPage
from moderation.models import ModerationItem, Risk, TargetType
from scrims import services as scrim_services
from scrims.models import Role, Scrim, ScrimFormat, ScrimStatus
from tournaments import registration as reg
from tournaments.models import Tournament, TournamentStatus
from tournaments.tests.test_state_table import make, player  # noqa: F401

PASSWORD = "Correct-Horse-Battery-1"


@pytest.fixture
def site(db):
    call_command("init_site", verbosity=0)
    cache.clear()


def _staff(email, *groups, superuser=False):
    user = User.objects.create_user(
        email=email,
        password=PASSWORD,
        nickname=email.split("@")[0][:12],
        is_superuser=superuser,
        agreed_terms_at=timezone.now(),
        agreed_cross_border_at=timezone.now(),
    )
    EmailAddress.objects.create(user=user, email=email, verified=True, primary=True)
    for name in groups:
        user.groups.add(Group.objects.get(name=name))
    return user


def _todo(client):
    html = client.get("/admin/").content.decode()
    start = html.find('id="site-todo-heading"')
    if start < 0:
        return None
    return html[start : html.find("</section>", start)]


def _flagged(**extra):
    values = {
        "target_type": TargetType.NICKNAME,
        "target_id": 1,
        "field": "nickname",
        "excerpt": "可疑的昵称",
        "text_hash": f"hash-{ModerationItem.objects.count()}",
        "risk": Risk.HIGH,
        "checked_at": timezone.now(),
    }
    values.update(extra)
    return ModerationItem.objects.create(**values)


def _individual_tournament(title="编队杯"):
    now = timezone.now()
    return Tournament.objects.create(
        title=title,
        registration_mode="individual",
        registration_opens_at=now - timedelta(days=1),
        registration_closes_at=now + timedelta(days=7),
        roster_min=2,
        roster_max=3,
        status=TournamentStatus.PUBLISHED,
        published_at=now,
    )


def _pool_entry(tournament, email, nickname):
    user = player(email, nickname)
    return reg.sign_up_individual(
        tournament=tournament,
        user=user,
        game_account_id=user.game_accounts.first().pk,
        roles=["tank"],
    )


def _closed_scrim(title="待分队内战"):
    now = timezone.now()
    return Scrim.objects.create(
        title=title,
        format=ScrimFormat.RQ_5V5,
        status=ScrimStatus.PUBLISHED,
        starts_at=now + timedelta(hours=3),
        signup_closes_at=now - timedelta(hours=1),
    )


# --- the dashboard's to-do --------------------------------------------


@pytest.mark.django_db
def test_nothing_of_the_trusted_waits_on_the_list(site, client):
    """v6.72–v6.73: AI findings come by mail, faces and articles go out at
    once, so none of them is work on the dashboard any more."""
    _flagged()
    member = player("face118@example.com", "换头像的人")
    AvatarSubmission.objects.create(user=member)  # one left from before
    client.force_login(_staff("editor118@example.com", "内容编辑"))
    todo = _todo(client)
    for gone in ("内容等待复核", "头像等待审核", "稿件等待审核", "报名"):
        assert gone not in todo


@pytest.mark.django_db
def test_tournament_managers_see_registrations_and_the_pool(site, client, make):  # noqa: F811
    make()  # one pending team registration
    tournament = _individual_tournament("新人编队杯")
    _pool_entry(tournament, "pool118@example.com", "散人118")
    client.force_login(_staff("manager118@example.com", "赛事管理员", GROUP_SUBMITTER))
    todo = _todo(client)
    assert "1 份报名等待审核" in todo
    assert "「新人编队杯」有 1 人等待编队" in todo
    assert reverse("tournament_teams_board", args=[tournament.pk]) in todo
    assert "内容等待复核" not in todo


@pytest.mark.django_db
def test_scrim_managers_see_closed_scrims_without_teams(site, client):
    scrim = _closed_scrim()
    client.force_login(_staff("scrimmer118@example.com", "内战管理员"))
    assert "「待分队内战」报名已截止，还没分队" in _todo(client)
    user = player("split118@example.com", "上场者")
    signup = scrim_services.sign_up(
        scrim=scrim,
        user=user,
        game_account_id=user.game_accounts.first().pk,
        roles=[Role.DAMAGE],
        now=timezone.now() - timedelta(hours=2),
    )
    signup.team = "a"
    signup.save(update_fields=["team"])
    assert "待分队内战" not in _todo(client)


@pytest.mark.django_db
def test_superusers_see_failed_static_pages(site, client):
    PrerenderedPage.objects.create(path="/broken/", kind="page", status="failed")
    client.force_login(_staff("root118@example.com", superuser=True))
    todo = _todo(client)
    assert "1 个静态页面生成失败" in todo
    assert "?status=failed" in todo


@pytest.mark.django_db
def test_nothing_waiting_says_so_and_people_without_queues_get_no_panel(site, client):
    client.force_login(_staff("calm118@example.com", "内容编辑"))
    assert "暂时没有待办" in _todo(client)
    client.force_login(_staff("author118@example.com", "认证作者", GROUP_SUBMITTER))
    assert _todo(client) is None


# --- the review queue --------------------------------------------------


@pytest.mark.django_db
def test_the_review_list_filters_by_time(site, client):
    _flagged(excerpt="昨天的可疑内容118")
    old = _flagged(excerpt="上个月的可疑内容118")
    ModerationItem.objects.filter(pk=old.pk).update(
        created_at=timezone.now() - timedelta(days=20)
    )
    client.force_login(_staff("filter118@example.com", "内容编辑"))
    week = client.get(reverse("moderation_index") + "?since=7").content.decode()
    assert "昨天的可疑内容118" in week
    assert "上个月的可疑内容118" not in week
    month = client.get(reverse("moderation_index") + "?since=30").content.decode()
    assert "上个月的可疑内容118" in month


@pytest.mark.django_db
def test_the_record_page_has_no_scan_button_and_says_how_alerts_come(site, client):
    """v6.72 (round 194): incremental patrol instead of a night-time full
    scan from a button; findings come by mail."""
    client.force_login(_staff("scanner194@example.com", "内容编辑"))
    html = client.get(reverse("moderation_index")).content.decode()
    assert "全量扫描" not in html
    assert "每 30 分钟巡查一次" in html
    assert "<title>巡查记录" in html


@pytest.mark.django_db
def test_the_scan_covers_teams_and_comments_too(site):
    from comments import services as comment_services
    from content.models import ArticleCategory, ArticleIndexPage, ArticlePage
    from moderation import integrations
    from teams import services as team_services

    captain = player("scan-captain118@example.com", "扫描队长")
    captain.motto = "冲就完了"
    captain.save(update_fields=["motto"])
    team = team_services.create_team(user=captain, name="扫描战队118")
    team.description = "我们招人"
    team.save(update_fields=["description"])
    news = ArticleIndexPage.objects.get(slug="news")
    article = ArticlePage(
        title="扫描文章118",
        slug="scan-118",
        category=ArticleCategory.objects.first(),
        author=captain,
        owner=captain,
        summary="摘要",
        body="正文",
    )
    news.add_child(instance=article)
    article.save_revision().publish()
    with mock.patch("comments.services._submit_moderation"):
        comment_services.create(
            page=ArticlePage.objects.get(pk=article.pk), author=captain, body="好文章"
        )
    sent = []
    with mock.patch.object(
        integrations.services,
        "submit",
        side_effect=lambda **kwargs: sent.append(kwargs["target_type"]) or object(),
    ):
        integrations.scan_existing()
    for kind in (
        "nickname",
        "motto",
        "article",
        "team_name",
        "team_description",
        "comment",
    ):
        assert kind in sent, kind


@pytest.mark.django_db
def test_every_handling_stays_on_record(site, client):
    item = _flagged()
    client.force_login(_staff("handler118@example.com", "内容编辑"))
    url = reverse("moderation_action", args=[item.pk])
    client.post(url, {"action": "handled", "handling_note": "第一次：已联系作者"})
    client.post(url, {"action": "ok", "handling_note": "第二次：作者改好了"})
    detail = client.get(reverse("moderation_detail", args=[item.pk])).content.decode()
    assert "第一次：已联系作者" in detail
    assert "第二次：作者改好了" in detail
    assert "已处置" in detail


# --- the scrim split page ----------------------------------------------


def _split_scrim_with_signups():
    scrim = Scrim.objects.create(
        title="分队页118",
        format=ScrimFormat.OPEN_5V5,
        status=ScrimStatus.PUBLISHED,
        starts_at=timezone.now() + timedelta(days=1),
    )
    signups = []
    for index in range(2):
        user = player(f"split-{index}-118@example.com", f"分队{index}")
        ContactMethod.objects.filter(user=user).update(value=f"8800{index}118")
        signups.append(
            scrim_services.sign_up(
                scrim=scrim,
                user=user,
                game_account_id=user.game_accounts.first().pk,
                roles=[Role.DAMAGE],
            )
        )
    return scrim, signups


@pytest.mark.django_db
def test_the_split_page_keeps_its_order_after_saving(site, client):
    scrim, _signups = _split_scrim_with_signups()
    client.force_login(_staff("order118@example.com", "内战管理员"))
    url = reverse("scrim_split", args=[scrim.pk])
    page = client.get(url + "?order=rating").content.decode()
    assert re.search(r'href="\?order=rating"[^>]*aria-current="true"', page)
    assert 'name="order" value="rating"' in page
    response = client.post(url, {"action": "select", "order": "rating"})
    assert response.url.endswith("?order=rating")


@pytest.mark.django_db
def test_scrim_managers_see_contacts_on_the_split_page(site, client):
    scrim, _signups = _split_scrim_with_signups()
    client.force_login(_staff("contacts118@example.com", "内战管理员"))
    page = client.get(reverse("scrim_split", args=[scrim.pk])).content.decode()
    assert "88000118" in page
    from django.contrib.auth.models import Permission

    bare = _staff("nocontacts118@example.com")
    bare.user_permissions.add(
        Permission.objects.get(codename="change_scrim"),
        Permission.objects.get(codename="access_admin"),
    )
    client.force_login(bare)
    page = client.get(reverse("scrim_split", args=[scrim.pk])).content.decode()
    assert "88000118" not in page


@pytest.mark.django_db
def test_the_split_result_has_a_copy_button(site, client):
    scrim, signups = _split_scrim_with_signups()
    for signup, team in zip(signups, ("a", "b"), strict=True):
        signup.is_selected = True
        signup.team = team
        signup.save(update_fields=["is_selected", "team"])
    client.force_login(_staff("copier118@example.com", "内战管理员"))
    page = client.get(reverse("scrim_split", args=[scrim.pk])).content.decode()
    assert "data-copy-button" in page
    script = Path(django_settings.BASE_DIR, "static/js/scrim-split.js").read_text(
        encoding="utf-8"
    )
    assert "navigator.clipboard.writeText" in script
    assert "[data-copy-button]" in script


# --- 「账号已停用」 (design 3.7) -----------------------------------------


@pytest.mark.django_db
def test_split_page_marks_deactivated_accounts(site, client):
    scrim, signups = _split_scrim_with_signups()
    for signup, team in zip(signups, ("a", "b"), strict=True):
        signup.is_selected = True
        signup.team = team
        signup.save(update_fields=["is_selected", "team"])
    User.objects.filter(pk=signups[0].user_id).update(is_active=False)
    client.force_login(_staff("marker118@example.com", "内战管理员"))
    page = client.get(reverse("scrim_split", args=[scrim.pk])).content.decode()
    assert "<td>分队0（账号已停用）</td>" in page
    assert 'split-card-name">分队0（账号已停用）' in page
    assert "分队1（账号已停用）" not in page


@pytest.mark.django_db
def test_registration_review_marks_deactivated_accounts(site, client, make):  # noqa: F811
    registration, _captain, _team, _selections = make()
    mate = registration.members.exclude(user=_captain).first().user
    User.objects.filter(pk=mate.pk).update(is_active=False)
    client.force_login(_staff("review118@example.com", "赛事管理员"))
    listing = client.get(reverse("registration_review_index")).content.decode()
    assert "名单里有 1 个账号已停用" in listing
    detail = client.get(
        reverse("registration_review_detail", args=[registration.pk])
    ).content.decode()
    assert f"{mate.nickname}（账号已停用）" in detail


@pytest.mark.django_db
def test_the_arrangement_board_marks_deactivated_accounts(site, client):
    tournament = _individual_tournament()
    entry = _pool_entry(tournament, "gone118@example.com", "停用散人")
    _pool_entry(tournament, "here118@example.com", "在场散人")
    User.objects.filter(pk=entry.user_id).update(is_active=False)
    client.force_login(_staff("board118@example.com", "赛事管理员"))
    page = client.get(
        reverse("tournament_teams_board", args=[tournament.pk])
    ).content.decode()
    assert "停用散人（账号已停用）" in page
    assert "在场散人（账号已停用）" not in page


@pytest.mark.django_db
def test_tournaments_long_started_ask_to_be_finished(site, client):
    """Round 142 (design 14.1, v6.37): a tournament never finishes by itself."""
    now = timezone.now()
    window = {
        "registration_opens_at": now - timedelta(days=20),
        "registration_closes_at": now - timedelta(days=10),
        "published_at": now - timedelta(days=20),
    }
    Tournament.objects.create(
        title="打完没标杯",
        starts_at=now - timedelta(days=4),
        status=TournamentStatus.PUBLISHED,
        **window,
    )
    Tournament.objects.create(
        title="昨天开赛杯",
        starts_at=now - timedelta(days=1),
        status=TournamentStatus.PUBLISHED,
        **window,
    )
    Tournament.objects.create(
        title="早就结束杯",
        starts_at=now - timedelta(days=9),
        status=TournamentStatus.FINISHED,
        **window,
    )
    client.force_login(_staff("finish142@example.com", "赛事管理员", GROUP_SUBMITTER))
    todo = _todo(client)
    assert "「打完没标杯」开赛已经 3 天以上" in todo
    assert reverse("tournaments:index") in todo
    assert "昨天开赛杯" not in todo
    assert "早就结束杯" not in todo
    client.force_login(_staff("editor142@example.com", "内容编辑"))
    assert "打完没标杯" not in _todo(client)


def _mail_task(attempt, *, status="FAILED", days_ago=1, error="ok"):
    from django_tasks_db.models import DBTaskResult

    when = timezone.now() - timedelta(days=days_ago)
    args = [{"to": ["x@example.com"]}] + ([attempt] if attempt else [])
    return DBTaskResult.objects.create(
        task_path="core.tasks.deliver_queued_email",
        status=status,
        args_kwargs={"args": args, "kwargs": {}},
        run_after=when,
        finished_at=when,
        backend_name="default",
        queue_name="default",
        exception_class_path="smtplib.SMTPAuthenticationError",
        traceback=f"Traceback (most recent call last):\n  ...\n{error}\n",
    )


@pytest.mark.django_db
def test_the_owner_hears_about_mail_that_never_went_out(site, client):
    """Round 150 (design 14.1, v6.43)."""
    from core.models import SiteSettings

    _mail_task(3, error="smtplib.SMTPAuthenticationError: (535, b'auth failed')")
    _mail_task(1)  # a retry is still coming
    _mail_task(3, days_ago=10)  # too long ago
    _mail_task(3, status="SUCCESSFUL")
    client.force_login(_staff("root150@example.com", superuser=True))
    todo = _todo(client)
    assert "最近 7 天有 1 封邮件重试后仍没发出去" in todo
    assert "SMTPAuthenticationError: (535" in todo
    settings_url = reverse(
        "wagtailsettings:edit", args=["core", "sitesettings", SiteSettings.load().pk]
    )
    assert settings_url in todo
    client.force_login(_staff("editor150@example.com", "内容编辑"))
    assert "邮件重试后仍没发出去" not in _todo(client)


@pytest.mark.django_db
def test_no_lost_mail_no_line(site, client):
    _mail_task(2)
    client.force_login(_staff("root150b@example.com", superuser=True))
    assert "邮件重试后仍没发出去" not in _todo(client)


@pytest.mark.django_db
def test_the_owner_hears_when_the_worker_is_down(site, client):
    """Round 151 (design 14.1, v6.44)."""
    from core.worker import write_worker_heartbeat

    client.force_login(_staff("root151@example.com", superuser=True))
    todo = _todo(client)
    assert "后台任务（worker）没在运行：心跳缺失" in todo
    assert 'href="/healthz"' in todo
    write_worker_heartbeat()
    assert "worker）没在运行" not in _todo(client)
    client.force_login(_staff("editor151@example.com", "内容编辑"))
    from django.core.cache import cache

    cache.clear()
    assert "worker）没在运行" not in _todo(client)


@pytest.mark.django_db
def test_the_owner_hears_about_missing_or_failed_backups(
    site, client, settings, tmp_path
):
    """Round 152 (design 16.7, v6.45)."""
    import json
    import os

    settings.BACKUP_ROOT = tmp_path
    client.force_login(_staff("root152@example.com", superuser=True))
    assert "还没有任何备份" in _todo(client)

    archive = tmp_path / "sjtu-ow-20261001-030000.tar.gz"
    archive.write_bytes(b"x")
    two_days = (timezone.now() - timedelta(hours=48)).timestamp()
    os.utime(archive, (two_days, two_days))
    assert "最近一次备份是 48 小时前" in _todo(client)

    os.utime(archive, None)
    assert "备份定时任务" not in _todo(client)
    (tmp_path / "last-backup.json").write_text(
        json.dumps({"offsite": "failed", "error": "上传失败：bucket says no"}),
        encoding="utf-8",
    )
    assert "最近一次备份的异地上传失败：上传失败：bucket says no" in _todo(client)


@pytest.mark.django_db
def test_the_owner_hears_when_the_ai_cannot_be_reached(site, client):
    """Round 153 (design 14.1, v6.46)."""
    now = timezone.now()
    _flagged(reason="调用失败：HTTP 401", checked_at=now - timedelta(hours=2))
    _flagged(reason="调用失败：HTTP 500", checked_at=now - timedelta(hours=30))
    _flagged(reason="疑似广告", checked_at=now - timedelta(hours=1))
    client.force_login(_staff("root153@example.com", superuser=True))
    todo = _todo(client)
    assert "AI 审核最近 24 小时有 1 次调用失败（HTTP 401）" in todo
    assert reverse("moderation_index") in todo
    client.force_login(_staff("editor153@example.com", "内容编辑"))
    assert "调用失败" not in _todo(client)
