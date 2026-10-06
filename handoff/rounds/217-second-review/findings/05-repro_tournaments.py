"""217 复核 05 赛事报名：复现脚本（只读业务代码，不改）。

在测试机上跑：
    bash scripts/remote-check.sh run uv run pytest -q -s -p no:cacheprovider \
        handoff/rounds/217-second-review/findings/05-repro_tournaments.py

每条 test 断言的是「问题存在」：绿 = 复现了。
"""

import csv
import io

import pytest
from django.contrib.auth.models import Group
from django.core import mail
from django.core.management import call_command

from accounts.models import User
from core.models import PrerenderedPage
from tournaments import registration as reg
from tournaments import services
from tournaments.models import (
    IndividualSignup,
    Registration,
    RegistrationStatus,
    TournamentStatus,
)
from tournaments.tests.test_adhoc_teams import (
    _admin,
    _existing,
    _layout,
    _pool,
    _tournament,
)
from tournaments.tests.test_review_admin import manager, site  # noqa: F401
from tournaments.tests.test_state_table import admin_user, make  # noqa: F401


def _board_manager(client):
    call_command("init_site", verbosity=0)
    user = _admin()
    user.is_staff = True
    user.save()
    user.groups.add(Group.objects.get(name="赛事管理员"))
    client.force_login(user)
    return user


# --- 05-1 编排页没有版本号：过期的页面一保存就把别人的改动整个撤掉 --------------------


@pytest.mark.django_db
def test_05_1a_stale_board_dissolves_a_team_formed_meanwhile(client):
    tournament = _tournament(roster_min=2, roster_max=3)
    e0, e1, e2, e3 = _pool(tournament, 4)
    _board_manager(client)
    # 管理员 A 打开编排页时四人都在散人池；他把 e2、e3 拖进「新队伍」。
    stale = {"action": "save", "name-new": "乙队"}
    for entry in (e0, e1):
        stale[f"team-{entry.pk}"] = ""
    for entry in (e2, e3):
        stale[f"team-{entry.pk}"] = "new"
    # 这期间管理员 B 编成了「甲队」。
    reg.form_teams(tournament=tournament, actor=_admin(), layout=_layout(("甲队", [e0, e1])))
    alpha = tournament.registrations.get(team_name="甲队")
    assert alpha.status == RegistrationStatus.APPROVED

    response = client.post(f"/admin/tournaments/{tournament.pk}/teams/", stale)
    print("stale POST:", response.status_code, response.get("Location"))

    alpha.refresh_from_db()
    print("甲队 after A's save:", alpha.status, list(alpha.members.all()))
    assert alpha.status == RegistrationStatus.WITHDRAWN  # 被 A 的旧页面解散
    assert IndividualSignup.objects.get(pk=e0.pk).registration is None
    assert tournament.registrations.filter(
        team_name="乙队", status=RegistrationStatus.APPROVED
    ).exists()


@pytest.mark.django_db
def test_05_1b_stale_board_puts_back_a_member_who_left(client):
    tournament = _tournament(roster_min=2, roster_max=3)
    entries = _pool(tournament, 3)
    reg.form_teams(tournament=tournament, actor=_admin(), layout=_layout(("一队", entries)))
    team = tournament.registrations.get()
    _board_manager(client)
    stale = {"action": "save", f"name-r{team.pk}": "一队"}
    for entry in entries:
        stale[f"team-{entry.pk}"] = f"r{team.pk}"
    # 编排页开着的时候，e0 在报名详情页自己退出了队伍。
    reg.leave(registration=team, user=entries[0].user)
    assert not team.members.filter(user=entries[0].user).exists()

    client.post(f"/admin/tournaments/{tournament.pk}/teams/", stale)

    print("e0 signup after stale save:", IndividualSignup.objects.get(pk=entries[0].pk).registration_id)
    assert IndividualSignup.objects.get(pk=entries[0].pk).registration_id == team.pk
    assert team.members.filter(user=entries[0].user).exists()


# --- 05-2 个人报名的赛事取消时，散人池里的人收不到任何信，事后也没法通知 -------------


@pytest.mark.django_db
def test_05_2_cancelling_tells_nobody_in_the_pool(django_capture_on_commit_callbacks):
    from core import services as core_services

    tournament = _tournament()
    _pool(tournament, 3)
    mail.outbox.clear()
    with django_capture_on_commit_callbacks(execute=True):
        services.cancel(tournament=tournament, actor=admin_user(), reason="场地取消")
    print("cancel recipients:", services.cancellation_recipients(tournament))
    print("mails:", len(mail.outbox))
    assert services.cancellation_recipients(tournament) == []
    assert len(mail.outbox) == 0
    problem = core_services.announcement_problem(
        "tournament", tournament, audience=core_services.PARTICIPANTS
    )
    print("「通知报名的人」 after cancel:", problem)
    assert problem == "发布之后才能通知报名的人。"


# --- 05-3 已结束的赛事还能「发布」回已发布，T7 的拦截随之失效 --------------------------


@pytest.mark.django_db
def test_05_3_a_finished_tournament_can_be_published_again(make):  # noqa: F811
    registration, *_ = make(RegistrationStatus.PENDING)
    tournament = registration.tournament
    tournament.status = TournamentStatus.FINISHED
    tournament.save(update_fields=["status"])
    with pytest.raises(reg.RegistrationError):
        reg.approve(registration=Registration.objects.get(pk=registration.pk), actor=admin_user())

    services.publish(tournament=tournament, actor=admin_user())
    tournament.refresh_from_db()
    print("status after publish:", tournament.status)
    assert tournament.status == TournamentStatus.PUBLISHED
    reg.approve(registration=Registration.objects.get(pk=registration.pk), actor=admin_user())
    assert Registration.objects.get(pk=registration.pk).status == RegistrationStatus.APPROVED


# --- 05-4 一支没动的队里有人停用，整张编排页都存不了 -----------------------------------


@pytest.mark.django_db
def test_05_4_untouched_team_with_deactivated_member_blocks_every_save():
    tournament = _tournament(roster_min=2, roster_max=3)
    e0, e1, e2, e3 = _pool(tournament, 4)
    reg.form_teams(tournament=tournament, actor=_admin(), layout=_layout(("一队", [e0, e1])))
    first = tournament.registrations.get()
    User.objects.filter(pk=e0.user_id).update(is_active=False)

    layout = [
        _existing(first, "一队", [e0, e1]),  # 原样不动
        {"registration_id": None, "name": "二队", "signup_ids": [e2.pk, e3.pk]},
    ]
    with pytest.raises(reg.RegistrationError) as caught:
        reg.form_teams(tournament=tournament, actor=_admin(), layout=layout)
    print("problems:", caught.value.problems)
    assert any("暂时无法参加赛事报名" in p for p in caught.value.problems)
    assert not tournament.registrations.filter(team_name="二队").exists()


# --- 05-5 在两支临时队伍之间挪人：被挪的人收到「移回了散人池」 -------------------------


@pytest.mark.django_db
def test_05_5_moving_between_teams_says_returned_to_pool(django_capture_on_commit_callbacks):
    tournament = _tournament(roster_min=1, roster_max=3)
    e0, e1, e2, e3 = _pool(tournament, 4)
    reg.form_teams(
        tournament=tournament,
        actor=_admin(),
        layout=_layout(("甲队", [e0, e1]), ("乙队", [e2, e3])),
    )
    alpha = tournament.registrations.get(team_name="甲队")
    beta = tournament.registrations.get(team_name="乙队")
    mail.outbox.clear()
    with django_capture_on_commit_callbacks(execute=True):
        result = reg.form_teams(
            tournament=tournament,
            actor=_admin(),
            layout=[
                _existing(alpha, "甲队", [e0]),
                _existing(beta, "乙队", [e2, e3, e1]),
            ],
        )
    print("result:", result)
    mover = e1.user.email
    to_mover = [m for m in mail.outbox if mover in m.to]
    for m in to_mover:
        print("to mover:", m.subject, "|", "移回了散人池" in m.body)
    assert result["returned"] == 1
    assert any("移回了散人池" in m.body for m in to_mover)
    assert IndividualSignup.objects.get(pk=e1.pk).registration_id == beta.pk


# --- 05-6 两支队互换队名被拒 ---------------------------------------------------------


@pytest.mark.django_db
def test_05_6_swapping_two_names_is_refused():
    tournament = _tournament(roster_min=1, roster_max=3)
    e0, e1 = _pool(tournament, 2)
    reg.form_teams(
        tournament=tournament, actor=_admin(), layout=_layout(("甲队", [e0]), ("乙队", [e1]))
    )
    alpha = tournament.registrations.get(team_name="甲队")
    beta = tournament.registrations.get(team_name="乙队")
    with pytest.raises(reg.RegistrationError) as caught:
        reg.form_teams(
            tournament=tournament,
            actor=_admin(),
            layout=[_existing(alpha, "乙队", [e0]), _existing(beta, "甲队", [e1])],
        )
    print("problems:", caught.value.problems)
    assert any("已经有了" in p for p in caught.value.problems)


# --- 05-7 编排页编成队伍（=报名已通过）不刷新首页 -------------------------------------


@pytest.mark.django_db
def test_05_7_forming_a_team_does_not_refresh_the_homepage(settings, tmp_path):
    settings.PRERENDER_ENABLED = True
    settings.PRERENDER_ROOT = tmp_path
    tournament = _tournament()
    entries = _pool(tournament, 2)
    PrerenderedPage.objects.all().delete()

    reg.form_teams(tournament=tournament, actor=_admin(), layout=_layout(("一队", entries)))

    paths = set(PrerenderedPage.objects.values_list("path", flat=True))
    print("requested after forming:", paths)
    assert tournament.get_absolute_url() in paths
    assert "/" not in paths  # 首页「已通过 N 队」不跟着变

    PrerenderedPage.objects.all().delete()
    reg.dissolve(registration=tournament.registrations.get(), actor=_admin())
    paths = set(PrerenderedPage.objects.values_list("path", flat=True))
    print("requested after dissolving:", paths)
    assert "/" in paths  # 对照：解散时刷新了首页


# --- 05-8 CSV 导出不防公式 -----------------------------------------------------------


@pytest.mark.django_db
def test_05_8_export_writes_a_formula_nickname_verbatim(client, make, manager):  # noqa: F811
    registration, captain, team, selections = make(RegistrationStatus.PENDING)
    mate = registration.members.exclude(is_captain=True).first().user
    User.objects.filter(pk=mate.pk).update(nickname="=1+1")
    reg.submit(
        tournament=registration.tournament, team=team, actor=captain, selections=selections
    )
    client.force_login(manager)
    from django.urls import reverse

    response = client.get(reverse("registration_review_export") + "?status=pending")
    assert response.status_code == 200
    rows = list(csv.reader(io.StringIO(response.content.decode("utf-8-sig"))))
    cells = [cell for row in rows[1:] for cell in row]
    print("cells starting with '=':", [c for c in cells if c.startswith("=")])
    assert "=1+1" in cells
