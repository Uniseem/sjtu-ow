"""Team emails (design 7.3, 7.4, 7.5), written as letters (10.3).

Each ``*_letter`` builds what one email says; the function without the suffix
sends it, one message per person, through the queued backend. The email
specimen page (/_styleguide/emails/) renders the builders with sample data.
"""

from __future__ import annotations

from core.letters import Letter, send, site_url


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
    send(application_submitted_letter(application), [captain])


def application_decided_letter(application) -> Letter:
    team = application.team
    reason = f"你收到这封邮件，是因为你申请过加入「{team.name}」。"
    if application.status == "approved":
        return Letter(
            subject=f"入队申请已通过：{team.name}",
            lead=f"你加入「{team.name}」的申请已通过，现在你是这支战队的队员了。",
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
    send(application_decided_letter(application), [application.applicant])


def member_removed_letter(team) -> Letter:
    return Letter(
        subject=f"你已被移出战队：{team.name}",
        lead=f"队长把你移出了战队「{team.name}」。",
        paragraphs=["如果有疑问，请直接联系队长。"],
        reason=f"你收到这封邮件，是因为你曾是战队「{team.name}」的队员。",
    )


def member_removed(team, user) -> None:
    send(member_removed_letter(team), [user])


def captain_changed_letter(team) -> Letter:
    return Letter(
        subject=f"你已成为队长：{team.name}",
        lead=f"你现在是战队「{team.name}」的队长。",
        paragraphs=["审批入队申请、管理成员、为战队报名比赛，都在战队管理页。"],
        action=("打开战队管理", _manage(team)),
        reason=f"你收到这封邮件，是因为你是战队「{team.name}」的成员。",
    )


def captain_changed(team, new_captain) -> None:
    send(captain_changed_letter(team), [new_captain])


def team_disbanded_letter(team) -> Letter:
    return Letter(
        subject=f"战队已解散：{team.name}",
        lead=f"战队「{team.name}」已经解散。",
        paragraphs=["还在等审批的入队申请也一并取消了。"],
        reason=f"你收到这封邮件，是因为你是战队「{team.name}」的成员。",
    )


def team_disbanded(team, members) -> None:
    send(team_disbanded_letter(team), members)
