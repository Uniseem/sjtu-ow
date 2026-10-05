"""Team emails (design 7.3, 7.4, 7.5), written as letters (10.3).

Each ``*_letter`` builds what one email says; the function without the suffix
sends it, one message per person, through the queued backend. The email
specimen page (/_styleguide/emails/) renders the builders with sample data.
"""

from __future__ import annotations

from core.letters import Letter, send, site_url
from core.outbox import hold


def _manage(team) -> str:
    return site_url(f"/teams/{team.pk}/manage/")


def application_submitted_letter(application) -> Letter:
    team = application.team
    applicant = application.applicant
    return Letter(
        subject=f"新的入队申请：{team.name}",
        lead=f"{applicant.nickname} 申请加入你的战队「{team.name}」，等你审批。",
        facts=[
            ("申请人", applicant.nickname),
            ("意向位置", "、".join(application.role_labels()) or "未填"),
            ("留言", application.message or "（无）"),
        ],
        action=("去审批", _manage(team)),
        reason=f"你收到这封邮件，是因为你是战队「{team.name}」的队长。",
    )


def application_submitted(application) -> None:
    captain = application.team.captain()
    if captain is None:
        return
    hold(application_submitted_letter(application), [captain])


def application_decided_letter(application) -> Letter:
    team = application.team
    reason = f"你收到这封邮件，是因为你申请过加入「{team.name}」。"
    if application.status == "approved":
        # Design 7.1 (v6.31): how to reach the team, if the captain said.
        contact = [("队内联系方式", team.member_contact)] if team.member_contact else []
        return Letter(
            subject=f"入队申请已通过：{team.name}",
            lead=f"你加入「{team.name}」的申请已通过，现在你是这支战队的队员了。",
            facts=contact,
            action=("打开战队主页", site_url(team.get_absolute_url())),
            reason=reason,
        )
    return Letter(
        subject=f"入队申请未通过：{team.name}",
        lead=f"你加入「{team.name}」的申请没有通过。",
        facts=[("原因", application.decision_note or "（队长没有填写）")],
        paragraphs=["你可以调整之后再申请，或者看看别的战队。"],
        action=("打开战队主页", site_url(team.get_absolute_url())),
        reason=reason,
    )


def application_decided(application) -> None:
    hold(application_decided_letter(application), [application.applicant])


def applications_waiting_letter(team, applications) -> Letter:
    """Design 7.3 (v6.39): a week in, before they close by themselves."""
    from teams.services import REMIND_CAPTAIN_DAYS, STALE_APPLICATION_DAYS

    left = STALE_APPLICATION_DAYS - REMIND_CAPTAIN_DAYS
    return Letter(
        subject=f"入队申请等你处理：{team.name}",
        lead=(
            f"「{team.name}」有 {len(applications)} 个入队申请等了 "
            f"{REMIND_CAPTAIN_DAYS} 天以上，再过 {left} 天没处理会自动关闭。"
        ),
        facts=[
            (a.applicant.nickname, "、".join(a.role_labels()) or "未填位置")
            for a in applications
        ],
        action=("去审批", _manage(team)),
        reason=f"你收到这封邮件，是因为你是战队「{team.name}」的队长。",
    )


def applications_waiting(team, applications, captain) -> None:
    send(applications_waiting_letter(team, applications), [captain])


def application_expired_letter(application) -> Letter:
    """Design 7.3 (v6.36): the captain never answered."""
    from teams.services import STALE_APPLICATION_DAYS

    team = application.team
    return Letter(
        subject=f"入队申请已关闭：{team.name}",
        lead=(
            f"你加入「{team.name}」的申请，队长 {STALE_APPLICATION_DAYS} 天没有处理，"
            "已经自动关闭。"
        ),
        paragraphs=["队长可能最近不在。你可以过一阵再申请，或者看看别的招募中的战队。"],
        action=("看看招募中的战队", site_url("/teams/?recruiting=1")),
        reason=f"你收到这封邮件，是因为你申请过加入「{team.name}」。",
    )


def application_expired(application) -> None:
    send(application_expired_letter(application), [application.applicant])


def member_removed_letter(team) -> Letter:
    return Letter(
        subject=f"你已被移出战队：{team.name}",
        lead=f"队长把你移出了战队「{team.name}」。",
        paragraphs=["如果有疑问，请直接联系队长。"],
        reason=f"你收到这封邮件，是因为你曾是战队「{team.name}」的队员。",
    )


def member_removed(team, user) -> None:
    hold(member_removed_letter(team), [user])


def member_left_letter(team, user, entries=()) -> Letter:
    """Design 7.4 (v6.26): the captain hears that someone left, and which
    submitted rosters still list them."""
    facts = [("退出的人", user.nickname)]
    paragraphs = []
    action = ("打开战队管理", _manage(team))
    if entries:
        from tournaments.notifications import moment

        for registration in entries:
            closes = moment(registration.tournament.registration_closes_at)
            facts.append(
                (
                    "还在报名名单里",
                    f"{registration.tournament.title}（报名截止 {closes}）",
                )
            )
        paragraphs.append(
            "已经提交的报名名单不会跟着战队变。报名截止前可以在报名详情页同步名单，"
            "截止以后请联系赛事管理员。"
        )
        action = ("查看报名详情", site_url(entries[0].get_absolute_url()))
    return Letter(
        subject=f"队员退出战队：{team.name}",
        lead=f"{user.nickname} 退出了战队「{team.name}」。",
        facts=facts,
        paragraphs=paragraphs,
        action=action,
        reason=f"你收到这封邮件，是因为你是战队「{team.name}」的队长。",
    )


def member_left(team, user) -> None:
    from tournaments.registration import entries_still_listing

    captain = team.captain()
    if captain is None:
        return
    hold(member_left_letter(team, user, entries_still_listing(team, user)), [captain])


def captain_changed_letter(team) -> Letter:
    return Letter(
        subject=f"你已成为队长：{team.name}",
        lead=f"你现在是战队「{team.name}」的队长。",
        paragraphs=["审批入队申请、管理成员、为战队报名比赛，都在战队管理页。"],
        action=("打开战队管理", _manage(team)),
        reason=f"你收到这封邮件，是因为你是战队「{team.name}」的成员。",
    )


def captain_changed(team, new_captain) -> None:
    hold(captain_changed_letter(team), [new_captain])


def team_disbanded_letter(team) -> Letter:
    return Letter(
        subject=f"战队已解散：{team.name}",
        lead=f"战队「{team.name}」已经解散。",
        paragraphs=["还在等审批的入队申请也一并取消了。"],
        reason=f"你收到这封邮件，是因为你是战队「{team.name}」的成员。",
    )


def team_disbanded(team, members) -> None:
    hold(team_disbanded_letter(team), members)
