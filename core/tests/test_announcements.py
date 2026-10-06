"""Round 123: 「通知全体成员」 (design 10.4, v6.19).

A tournament or scrim manager tells every member about a new event with one
click; members can turn these notices off, and every one carries a link to.
"""

from datetime import timedelta
from unittest import mock

import pytest
from allauth.account.models import EmailAddress
from django.contrib.auth.models import Group
from django.core.management import call_command
from django.urls import reverse
from django.utils import timezone

from accounts.models import User
from core import services
from core.models import Broadcast, SiteSettings
from scrims.models import Scrim, ScrimFormat, ScrimStatus
from tournaments.models import Tournament, TournamentStatus

PASSWORD = "Correct-Horse-Battery-1"


@pytest.fixture
def site(db):
    call_command("init_site", verbosity=0)
    row = SiteSettings.load()
    row.smtp_host = "smtp.example.com"
    row.from_address = "noreply@example.com"
    row.save()


def _member(email, *groups, verified=True, sjtu=False, **extra):
    user = User.objects.create_user(
        email=email,
        password=PASSWORD,
        nickname=email.split("@")[0][:12],
        is_sjtu=sjtu,
        agreed_terms_at=timezone.now(),
        agreed_cross_border_at=timezone.now(),
        **extra,
    )
    EmailAddress.objects.create(user=user, email=email, verified=verified, primary=True)
    for name in groups:
        user.groups.add(Group.objects.get(name=name))
    return user


def _tournament(**extra):
    now = timezone.now()
    values = {
        "title": "秋季校内杯",
        "summary": "五人一队，单败淘汰。",
        "registration_mode": "individual",
        "registration_opens_at": now - timedelta(days=1),
        "registration_closes_at": now + timedelta(days=7),
        "roster_min": 5,
        "roster_max": 6,
        "status": TournamentStatus.PUBLISHED,
        "published_at": now,
    }
    values.update(extra)
    return Tournament.objects.create(**values)


@pytest.fixture
def worker():
    """The worker's part, done on the spot: what announce() queues is
    delivered when the transaction commits."""

    def run(broadcast_id):
        services.deliver(Broadcast.objects.get(pk=broadcast_id))

    task = mock.Mock()
    task.enqueue.side_effect = run
    with mock.patch("core.tasks.send_broadcast", task):
        yield task


def _half_an_hour_later():
    """Design 10.4 (v7.20, 216 B11): the same one goes to everyone again only
    after 30 minutes; tests that send twice move the first one back."""
    Broadcast.objects.update(created_at=timezone.now() - timedelta(minutes=31))


def _send(django_capture_on_commit_callbacks, **kwargs):
    with django_capture_on_commit_callbacks(execute=True):
        return services.announce(**kwargs)


# --- who gets it -------------------------------------------------------


@pytest.mark.django_db
def test_only_active_verified_members_who_left_it_on(site):
    keen = _member("keen123@example.com")
    _member("muted123@example.com", accepts_announcements=False)
    _member("unverified123@example.com", verified=False)
    gone = _member("gone123@example.com")
    User.objects.filter(pk=gone.pk).update(is_active=False)
    emails = set(services.announcement_recipients().values_list("email", flat=True))
    assert emails == {keen.email}


@pytest.mark.django_db
def test_sjtu_only_events_tell_sjtu_members_only(site):
    _member("sjtu123@example.com", sjtu=True)
    _member("outside123@example.com", sjtu=False)
    assert services.recipient_count(_tournament(sjtu_only=True)) == 1
    assert services.recipient_count(_tournament(title="公开杯")) == 2


# --- sending -----------------------------------------------------------


@pytest.mark.django_db
def test_a_manager_tells_everyone_and_may_again(
    site, worker, mailoutbox, django_capture_on_commit_callbacks
):
    manager = _member("manager123@example.com", "赛事管理员")
    member = _member("player123@example.com")
    tournament = _tournament()
    broadcast = _send(
        django_capture_on_commit_callbacks,
        kind="tournament",
        obj=tournament,
        actor=manager,
    )
    assert broadcast.recipient_count == 2
    to = sorted(address for message in mailoutbox for address in message.to)
    assert to == sorted([manager.email, member.email])
    letter = next(message for message in mailoutbox if message.to == [member.email])
    assert "新赛事：秋季校内杯" in letter.subject
    assert "五人一队" in letter.body
    assert "/tournaments/" in letter.body
    unsubscribe = services.unsubscribe_url(member)
    assert unsubscribe in letter.body
    assert letter.extra_headers["List-Unsubscribe"] == f"<{unsubscribe}>"
    assert letter.extra_headers["List-Unsubscribe-Post"] == "List-Unsubscribe=One-Click"
    assert "之前已经发过" not in letter.body  # the first one says nothing
    # v7.5: it may go out again, and from the second one the letter says so.
    mailoutbox.clear()
    _half_an_hour_later()
    again = _send(
        django_capture_on_commit_callbacks,
        kind="tournament",
        obj=tournament,
        actor=manager,
    )
    assert again.before == 1 and Broadcast.objects.count() == 2
    second = next(message for message in mailoutbox if message.to == [member.email])
    notice = "关于这场赛事「秋季校内杯」，之前已经发过 1 次邮件，这次可能有修改"
    assert second.body.index(notice) < second.body.index("五人一队")
    html = dict((mime, c) for c, mime in second.alternatives)["text/html"]
    assert "data-letter-notice" in html and notice in html


@pytest.mark.django_db
def test_no_smtp_no_drafts_no_strangers(site):
    manager = _member("manager123b@example.com", "赛事管理员")
    draft = _tournament(
        title="草稿杯", status=TournamentStatus.DRAFT, published_at=None
    )
    with pytest.raises(services.AnnouncementError, match="发布之后"):
        services.announce(kind="tournament", obj=draft, actor=manager)
    scrimmer = _member("scrimmer123@example.com", "内战管理员")
    with pytest.raises(services.AnnouncementError, match="管理权限"):
        services.announce(kind="tournament", obj=_tournament(), actor=scrimmer)
    row = SiteSettings.load()
    row.smtp_host = ""
    row.save()
    with pytest.raises(services.AnnouncementError, match="SMTP"):
        services.announce(
            kind="tournament", obj=_tournament(title="无信杯"), actor=manager
        )
    assert not Broadcast.objects.exists()


@pytest.mark.django_db
def test_people_who_turned_it_off_meanwhile_are_skipped(site, mailoutbox):
    manager = _member("manager123c@example.com", "内战管理员")
    member = _member("player123c@example.com")
    scrim = Scrim.objects.create(
        title="周五内战",
        format=ScrimFormat.OPEN_5V5,
        status=ScrimStatus.PUBLISHED,
        starts_at=timezone.now() + timedelta(days=2),
    )
    broadcast = Broadcast.objects.create(
        kind="scrim", object_id=scrim.pk, subject="新内战：周五内战", sent_by=manager
    )
    services.set_announcements(member, False)
    services.deliver(broadcast)
    assert [message.to for message in mailoutbox] == [[manager.email]]
    assert "新内战：周五内战" in mailoutbox[0].subject


# --- the admin ---------------------------------------------------------


@pytest.mark.django_db
def test_the_admin_previews_then_sends(
    site, worker, client, mailoutbox, django_capture_on_commit_callbacks
):
    manager = _member("manager123d@example.com", "赛事管理员")
    _member("player123d@example.com")
    tournament = _tournament()
    client.force_login(manager)
    url = reverse("announce", args=["tournament", tournament.pk])
    page = client.get(url).content.decode()
    assert "2 人" in page
    assert "新赛事：秋季校内杯" in page
    with django_capture_on_commit_callbacks(execute=True):
        client.post(url)
    assert len(mailoutbox) == 2
    _half_an_hour_later()
    again = client.get(url).content.decode()
    assert "data-announce-again" in again and "之前发过 1 次" in again
    assert "关于这场赛事「秋季校内杯」，之前已经发过 1 次邮件" in again  # the preview
    assert "disabled" not in again.split("发给 2 人")[0].rsplit("<button", 1)[1]
    listing = client.get(reverse("tournaments:index")).content.decode()
    assert url in listing and "通知全体成员（发过 1 次）" in listing
    assert f"{url}?to=participants" in listing and ">通知报名的人<" in listing


@pytest.mark.django_db
def test_publishing_can_tell_everyone(
    site, worker, client, mailoutbox, django_capture_on_commit_callbacks
):
    manager = _member("manager123e@example.com", "赛事管理员")
    _member("player123e@example.com")
    quiet = _tournament(
        title="不通知杯", status=TournamentStatus.DRAFT, published_at=None
    )
    loud = _tournament(title="通知杯", status=TournamentStatus.DRAFT, published_at=None)
    client.force_login(manager)
    page = client.get(
        reverse("tournament_action", args=[loud.pk, "publish"])
    ).content.decode()
    assert "发布后同时通知全体成员（2 人）" in page
    with django_capture_on_commit_callbacks(execute=True):
        client.post(reverse("tournament_action", args=[quiet.pk, "publish"]))
    assert mailoutbox == []
    with django_capture_on_commit_callbacks(execute=True):
        client.post(
            reverse("tournament_action", args=[loud.pk, "publish"]), {"announce": "1"}
        )
    assert len(mailoutbox) == 2
    assert Broadcast.objects.get().object_id == loud.pk


@pytest.mark.django_db
def test_scrim_managers_cannot_announce_tournaments(site, client):
    client.force_login(_member("scrimmer123f@example.com", "内战管理员"))
    response = client.get(reverse("announce", args=["tournament", _tournament().pk]))
    assert response.status_code in (302, 403)


# --- turning it off ----------------------------------------------------


@pytest.mark.django_db
def test_the_unsubscribe_link_asks_then_turns_it_off(site, client):
    member = _member("leaving123@example.com")
    url = services.unsubscribe_url(member).split("localhost:8000")[-1]
    page = client.get(url)
    assert page.status_code == 200
    assert "确定不再接收活动通知" in page.content.decode()
    member.refresh_from_db()
    assert member.accepts_announcements
    done = client.post(url)
    assert "已经退订" in done.content.decode()
    member.refresh_from_db()
    assert not member.accepts_announcements


@pytest.mark.django_db
def test_a_mail_client_can_unsubscribe_in_one_click(site):
    from django.test import Client

    member = _member("oneclick123@example.com")
    path = services.unsubscribe_url(member).split("localhost:8000")[-1]
    strict = Client(enforce_csrf_checks=True)
    response = strict.post(path, {"List-Unsubscribe": "One-Click"})
    assert response.status_code == 200
    member.refresh_from_db()
    assert not member.accepts_announcements


@pytest.mark.django_db
def test_a_tampered_link_does_nothing(site, client):
    member = _member("tamper123@example.com")
    token = services.unsubscribe_token(member)
    response = client.post(f"/unsubscribe/{token[:-2]}xx/")
    assert response.status_code == 404
    member.refresh_from_db()
    assert member.accepts_announcements


@pytest.mark.django_db
def test_members_switch_it_in_account_security(site, client):
    member = _member("switch123@example.com")
    client.force_login(member)
    page = client.get(reverse("me_security")).content.decode()
    assert "关闭活动通知" in page
    client.post(reverse("me_notifications"), {"accepts_announcements": "0"})
    member.refresh_from_db()
    assert not member.accepts_announcements
    assert "打开活动通知" in client.get(reverse("me_security")).content.decode()
    client.post(reverse("me_notifications"), {"accepts_announcements": "1"})
    member.refresh_from_db()
    assert member.accepts_announcements


def test_both_notices_are_on_the_specimen_page():
    from core.email_samples import sample

    for key in ("new-tournament", "new-scrim", "new-article"):
        found = sample(key)
        assert found is not None, key
        assert "退订活动通知" in found.text


@pytest.mark.django_db
def test_the_worker_task_delivers(site, mailoutbox):
    from core.tasks import send_broadcast

    manager = _member("manager123g@example.com", "赛事管理员")
    tournament = _tournament(title="任务杯")
    broadcast = Broadcast.objects.create(
        kind="tournament",
        object_id=tournament.pk,
        subject="新赛事：任务杯",
        sent_by=manager,
    )
    send_broadcast.call(broadcast.pk)
    assert [message.to for message in mailoutbox] == [[manager.email]]


@pytest.mark.django_db
def test_a_deactivated_account_link_is_dead(site, client):
    member = _member("stopped123@example.com")
    path = services.unsubscribe_url(member).split("localhost:8000")[-1]
    User.objects.filter(pk=member.pk).update(is_active=False)
    assert client.get(path).status_code == 404


# --- articles (v6.23) --------------------------------------------------


def _article(author, title="秋季招新"):
    from content.models import ArticleCategory, ArticleIndexPage, ArticlePage

    news = ArticleIndexPage.objects.get(slug="news")
    page = ArticlePage(
        title=title,
        slug=f"recruit-{ArticlePage.objects.count()}",
        category=ArticleCategory.objects.get(slug="notice"),
        author=author,
        owner=author,
        summary="面向全校，不限段位。",
        body="正文",
    )
    news.add_child(instance=page)
    page.save_revision().publish()
    return ArticlePage.objects.get(pk=page.pk)


@pytest.mark.django_db
def test_content_editors_announce_an_article(
    site, worker, client, mailoutbox, django_capture_on_commit_callbacks
):
    editor = _member("editor123@example.com", "内容编辑")
    member = _member("reader123@example.com")
    page = _article(editor)
    explore = reverse("backoffice:articles")
    announce = reverse("announce", args=["article", page.pk])
    edit = reverse("backoffice:article_edit", args=[page.pk])
    client.force_login(editor)
    assert announce in client.get(explore).content.decode()
    assert announce in client.get(edit).content.decode()
    preview = client.get(announce).content.decode()
    assert "公告：秋季招新" in preview
    with django_capture_on_commit_callbacks(execute=True):
        client.post(announce)
    letter = next(message for message in mailoutbox if message.to == [member.email])
    assert letter.subject.endswith("公告：秋季招新")
    assert "面向全校" in letter.body
    assert page.url in letter.body
    # v7.5: still there after it went out, saying how often it has.
    assert "通知全体成员（发过 1 次）" in client.get(explore).content.decode()
    assert "通知全体成员（发过 1 次）" in client.get(edit).content.decode()
    mailoutbox.clear()
    _half_an_hour_later()
    with django_capture_on_commit_callbacks(execute=True):
        client.post(announce)
    again = next(message for message in mailoutbox if message.to == [member.email])
    assert "关于这篇文章「秋季招新」，之前已经发过 1 次邮件" in again.body


@pytest.mark.django_db
def test_drafts_and_other_roles_cannot_announce_articles(site, client):
    editor = _member("editor123b@example.com", "内容编辑")
    page = _article(editor, title="草稿招新")
    page.unpublish()
    announce = reverse("announce", args=["article", page.pk])
    client.force_login(editor)
    explore = reverse("backoffice:articles")
    assert announce not in client.get(explore).content.decode()
    with pytest.raises(services.AnnouncementError, match="发布之后"):
        services.announce(kind="article", obj=page, actor=editor)
    manager = _member("manager123h@example.com", "赛事管理员")
    client.force_login(manager)
    response = client.get(announce)
    assert response.status_code in (302, 403)
    live = _article(editor, title="已发布招新")
    client.force_login(_member("writer123@example.com", "投稿者"))
    listing = client.get(explore)
    assert listing.status_code == 200
    assert (
        reverse("announce", args=["article", live.pk]) not in listing.content.decode()
    )
    assert client.get(reverse("announce", args=["article", live.pk])).status_code == 403


# --- planned articles (v6.54) --------------------------------------------


def _planned(author, go_live_at, title="周五招新"):
    from content.models import ArticleCategory, ArticleIndexPage, ArticlePage

    news = ArticleIndexPage.objects.get(slug="news")
    page = ArticlePage(
        title=title,
        slug=f"planned-{ArticlePage.objects.count()}",
        category=ArticleCategory.objects.get(slug="notice"),
        author=author,
        owner=author,
        summary="周五晚上八点见。",
        body="正文",
        live=False,
    )
    news.add_child(instance=page)
    page.go_live_at = go_live_at
    page.save_revision().publish()
    page = ArticlePage.objects.get(pk=page.pk)
    assert not page.live  # Wagtail only noted the time
    return page


@pytest.mark.django_db
def test_a_planned_article_is_announced_when_it_goes_live(
    site, worker, client, mailoutbox, django_capture_on_commit_callbacks
):
    from content.services import publish_due_pages

    editor = _member("editor165@example.com", "内容编辑")
    member = _member("reader165@example.com")
    go_live_at = timezone.now() + timedelta(hours=3)
    page = _planned(editor, go_live_at)
    explore = reverse("backoffice:articles")
    announce = reverse("announce", args=["article", page.pk])
    client.force_login(editor)
    listing = client.get(explore).content.decode()
    assert announce in listing and "上线时通知全体成员" in listing
    preview = client.get(announce).content.decode()
    assert "data-announce-on-publish" in preview and "上线时发" in preview
    assert f"{timezone.localtime(go_live_at):%H:%M} 上线" in preview

    with django_capture_on_commit_callbacks(execute=True):
        client.post(announce)
    assert mailoutbox == []
    broadcast = Broadcast.objects.get(kind="article", object_id=page.pk)
    assert broadcast.waits_for_publish and broadcast.recipient_count == 0
    assert announce not in client.get(explore).content.decode()
    with pytest.raises(services.AnnouncementError, match="上线时"):
        services.announce(kind="article", obj=page, actor=editor)

    late = _member("late165@example.com")  # joins before it goes live
    later = go_live_at + timedelta(seconds=30)
    with mock.patch("django.utils.timezone.now", return_value=later):
        with django_capture_on_commit_callbacks(execute=True):
            assert publish_due_pages()
    broadcast.refresh_from_db()
    assert not broadcast.waits_for_publish and broadcast.recipient_count == 3
    to = sorted(address for message in mailoutbox for address in message.to)
    assert to == sorted([editor.email, member.email, late.email])
    assert all(message.subject.endswith("公告：周五招新") for message in mailoutbox)


@pytest.mark.django_db
def test_publishing_a_planned_article_by_hand_sends_it_too(
    site, worker, mailoutbox, django_capture_on_commit_callbacks
):
    editor = _member("editor165b@example.com", "内容编辑")
    page = _planned(editor, timezone.now() + timedelta(days=2), title="提前上线")
    with django_capture_on_commit_callbacks(execute=True):
        services.announce(kind="article", obj=page, actor=editor)
    assert mailoutbox == []
    page.go_live_at = None
    with django_capture_on_commit_callbacks(execute=True):
        page.save_revision().publish()
    assert [message.to for message in mailoutbox] == [[editor.email]]
    # Going live again later sends nothing more.
    with django_capture_on_commit_callbacks(execute=True):
        page.save_revision().publish()
    assert len(mailoutbox) == 1


# --- 「通知报名的人」 (round 201, v7.5) -------------------------------------


@pytest.mark.django_db
def test_articles_have_nobody_signed_up_and_a_note_has_a_limit(site, client):
    editor = _member("editor201@example.com", "内容编辑")
    page = _article(editor)
    client.force_login(editor)
    url = reverse("announce", args=["article", page.pk]) + "?to=participants"
    assert client.get(url).status_code == 404
    manager = _member("manager201@example.com", "赛事管理员")
    with pytest.raises(services.AnnouncementError, match="最多 500 字"):
        services.announce(
            kind="tournament",
            obj=_tournament(),
            actor=manager,
            audience="participants",
            note="字" * 501,
        )
    assert not Broadcast.objects.exists()


@pytest.mark.django_db
def test_an_unknown_kind_is_404(site, client):
    """An unregistered announce kind is a 404, not a crash (213, guard census)."""
    client.force_login(_member("kind213@example.com"))
    assert client.get(reverse("announce", args=["nosuch", 1])).status_code == 404
