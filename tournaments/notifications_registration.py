"""Registration emails (design 10.2), written as letters (10.3).

A team registration writes to its captain; an ad-hoc team (design 8.8.2)
has no captain, so every member on the roster hears about it. One message
per person. ``*_letter`` builds what an email says; the function without the
suffix sends it (see teams.notifications).
"""

from __future__ import annotations

from core.letters import Letter, send, site_url
from tournaments.models import RegistrationAction, RegistrationStatus

SUBMIT_SUBJECTS = {
    RegistrationAction.SUBMIT: "报名已提交",
    RegistrationAction.RESUBMIT: "报名已重新提交",
    RegistrationAction.SYNC_ROSTER: "报名名单已同步",
}


def recipients(registration) -> list:
    """The captain, or every member of an ad-hoc team (design 8.8.2)."""
    if registration.team_id is not None:
        captain = registration.team.captain()
        return [captain] if captain is not None and captain.email else []
    users = [row.user for row in registration.members.select_related("user")]
    return [user for user in users if user.email and user.is_active]


def _details(registration) -> tuple[str, str]:
    return ("查看报名详情", site_url(registration.get_absolute_url()))


def _why(registration) -> str:
    if registration.team_id is None:
        return (
            f"你收到这封邮件，是因为你在「{registration.tournament.title}」的"
            f"临时队伍「{registration.team_name}」里。"
        )
    return f"你收到这封邮件，是因为你是战队「{registration.team_name}」的队长。"


def registration_submitted_letter(registration, action) -> Letter:
    title = registration.tournament.title
    if registration.status == RegistrationStatus.APPROVED:
        lead = (
            f"「{registration.team_name}」报名「{title}」的名单已提交，并且已经通过。"
        )
    else:
        lead = (
            f"「{registration.team_name}」报名「{title}」的名单已提交，"
            f"等赛事管理员审核。"
        )
    return Letter(
        subject=f"{SUBMIT_SUBJECTS.get(action, '报名已提交')}：{title}",
        lead=lead,
        facts=[
            ("赛事", title),
            ("队伍", registration.team_name),
            ("名单版本", str(registration.roster_version)),
            ("当前状态", registration.get_status_display()),
        ],
        paragraphs=["名单里新加的队员会各收到一封通知，不需要他们确认。"]
        if registration.team_id
        else [],
        action=_details(registration),
        reason=_why(registration),
    )


def registration_submitted(registration, action) -> None:
    send(registration_submitted_letter(registration, action), recipients(registration))


def team_member_entered_letter(registration, row) -> Letter:
    """Design 8.3 (v5.3): the captain enters the whole team and nobody
    confirms, so the member hears which team, which game ID and where things
    stand."""
    title = registration.tournament.title
    captain = registration.submitted_by
    by = f"队长 {captain.nickname} " if captain is not None else "队长"
    return Letter(
        subject=f"你已被报名参加：{title}",
        lead=f"{by}为战队「{registration.team_name}」报名了「{title}」，你在名单里。",
        facts=[
            ("赛事", title),
            ("队伍", registration.team_name),
            ("你的游戏 ID", row.battletag or "未填"),
            ("当前状态", registration.get_status_display()),
        ],
        paragraphs=["整队报名不需要你确认。不想参加的话，请在报名截止前联系队长。"],
        action=_details(registration),
        reason=f"你收到这封邮件，是因为你是战队「{registration.team_name}」的队员。",
    )


def team_members_entered(registration, rows) -> None:
    """One message each, since the game ID differs."""
    for row in rows:
        send(team_member_entered_letter(registration, row), [row.user])


def registration_status_changed_letter(registration, note="") -> Letter:
    title = registration.tournament.title
    label = registration.get_status_display()
    if registration.status == RegistrationStatus.APPROVED:
        lead = f"「{registration.team_name}」报名「{title}」已通过审核。"
    else:
        lead = f"「{registration.team_name}」报名「{title}」的状态变成了：{label}。"
    paragraphs = []
    if registration.status == RegistrationStatus.REJECTED and registration.team_id:
        paragraphs.append("你可以按备注修改后，在报名截止前重新提交。")
    facts = [("赛事", title), ("队伍", registration.team_name)]
    starts_at = registration.tournament.starts_at
    if registration.status == RegistrationStatus.APPROVED and starts_at:
        # Design 8.1 (v6.24): the approval says when to show up.
        from tournaments.notifications import moment

        facts.append(("比赛时间", moment(starts_at)))
    return Letter(
        subject=f"报名{label}：{title}",
        lead=lead,
        facts=facts + ([("备注", note)] if note else []),
        paragraphs=paragraphs,
        action=_details(registration),
        reason=_why(registration),
    )


def registration_status_changed(registration, note="") -> None:
    send(
        registration_status_changed_letter(registration, note),
        recipients(registration),
    )


# --- ad-hoc teams (design 8.8.2) ------------------------------------------------


def adhoc_team_formed_letter(registration) -> Letter:
    title = registration.tournament.title
    facts = [("赛事", title), ("队伍", registration.team_name)]
    if registration.tournament.starts_at:
        # Design 8.1 (v6.29): placed after the reminder went out, they still
        # learn when to show up.
        from tournaments.notifications import moment

        facts.append(("比赛时间", moment(registration.tournament.starts_at)))
    return Letter(
        subject=f"已编入临时队伍：{title}",
        lead=(
            f"赛事管理员把你编入了「{title}」的临时队伍"
            f"「{registration.team_name}」，报名已通过。"
        ),
        facts=facts,
        paragraphs=["报名截止前，你可以在报名详情页退出队伍，回到散人池。"],
        action=_details(registration),
        reason=f"你收到这封邮件，是因为你个人报名了「{title}」。",
    )


def adhoc_team_formed(registration, users) -> None:
    """Each newly placed member hears which team they are on."""
    send(adhoc_team_formed_letter(registration), users)


def adhoc_members_returned_letter(tournament, team_name, *, dissolved=False) -> Letter:
    if dissolved:
        lead = f"临时队伍「{team_name}」已由赛事管理员解散，你回到了散人池。"
    else:
        lead = f"赛事管理员把你从临时队伍「{team_name}」移回了散人池。"
    return Letter(
        subject=f"临时队伍有变化：{tournament.title}",
        lead=lead,
        facts=[("赛事", tournament.title), ("原来的队伍", team_name)],
        paragraphs=["你的个人报名还在，重新编队后会再通知你。"],
        action=("查看赛事页面", site_url(tournament.get_absolute_url())),
        reason=f"你收到这封邮件，是因为你个人报名了「{tournament.title}」。",
    )


def adhoc_members_returned(tournament, team_name, users, *, dissolved=False) -> None:
    """Admins moved these people back to the pool, or dissolved the team."""
    send(
        adhoc_members_returned_letter(tournament, team_name, dissolved=dissolved),
        users,
    )


def adhoc_member_left_letter(registration, user, *, dissolved=False) -> Letter:
    title = registration.tournament.title
    return Letter(
        subject=f"临时队伍成员退出：{title}",
        lead=(
            f"{user.nickname} 退出了「{title}」的临时队伍"
            f"「{registration.team_name}」，回到散人池。"
        ),
        facts=[
            ("赛事", title),
            ("队伍", registration.team_name),
            ("退出的人", user.nickname),
        ],
        paragraphs=["队伍里没有人了，已自动解散。"] if dissolved else [],
        action=(
            "打开队伍编排",
            site_url(f"/admin/tournaments/{registration.tournament_id}/teams/"),
        ),
        reason="你收到这封邮件，是因为你是赛事管理员。",
    )


def adhoc_member_left(registration, user, *, dissolved=False) -> None:
    """Tournament admins hear when someone leaves an ad-hoc team."""
    from core.mail import emails_for_groups
    from tournaments.services import MANAGER_GROUP

    send(
        adhoc_member_left_letter(registration, user, dissolved=dissolved),
        emails_for_groups([MANAGER_GROUP]),
    )
