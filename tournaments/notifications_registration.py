"""Registration emails (design 10.2). One message per recipient.

A team registration writes to its captain; an ad-hoc team (design 8.8.2)
has no captain, so every member on the roster hears about it.
"""

from __future__ import annotations

from django.core.mail import send_mail

from tournaments.models import RegistrationAction, RegistrationStatus
from tournaments.notifications import site_url

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


def _send(subject: str, body: str, users) -> None:
    for user in users:
        if not getattr(user, "email", ""):
            continue
        send_mail(
            subject=subject,
            message=body,
            from_email=None,
            recipient_list=[user.email],
            fail_silently=False,
        )


def registration_submitted(registration, action) -> None:
    subject = SUBMIT_SUBJECTS.get(action, "报名已提交")
    body = (
        f"「{registration.team_name}」报名「{registration.tournament.title}」"
        f"的名单已提交，当前状态：{registration.get_status_display()}。\n\n"
        f"名单版本：{registration.roster_version}\n"
        f"报名详情：{site_url(registration.get_absolute_url())}"
    )
    _send(subject, body, recipients(registration))


def registration_status_changed(registration, note="") -> None:
    label = registration.get_status_display()
    lines = [
        f"「{registration.team_name}」报名「{registration.tournament.title}」"
        f"的状态变成了：{label}。",
    ]
    if note:
        lines.append(f"备注：{note}")
    if registration.status == RegistrationStatus.REJECTED and registration.team_id:
        lines.append("你可以修改后重新提交（报名截止前）。")
    lines.append(f"报名详情：{site_url(registration.get_absolute_url())}")
    _send("报名状态有更新", "\n\n".join(lines), recipients(registration))


# --- ad-hoc teams (design 8.8.2) ------------------------------------------------


def adhoc_team_formed(registration, users) -> None:
    """Each newly placed member hears which team they are on."""
    body = (
        f"赛事管理员把你编入了「{registration.tournament.title}」的临时队伍"
        f"「{registration.team_name}」，报名已通过。\n\n"
        f"报名截止前可以在报名详情页退出队伍。\n"
        f"报名详情：{site_url(registration.get_absolute_url())}"
    )
    _send("已编入临时队伍", body, users)


def adhoc_members_returned(tournament, team_name, users, *, dissolved=False) -> None:
    """Admins moved these people back to the pool, or dissolved the team."""
    if dissolved:
        first = f"临时队伍「{team_name}」已由赛事管理员解散，你回到了散人池。"
    else:
        first = f"赛事管理员把你从临时队伍「{team_name}」移回了散人池。"
    body = (
        f"{first}\n\n"
        f"赛事：{tournament.title}\n"
        f"重新编队后会再通知你。\n"
        f"赛事页面：{site_url(tournament.get_absolute_url())}"
    )
    _send("临时队伍有变化", body, users)


def adhoc_member_left(registration, user, *, dissolved=False) -> None:
    """Tournament admins hear when someone leaves an ad-hoc team."""
    from core.mail import emails_for_groups
    from tournaments.services import MANAGER_GROUP

    lines = [
        f"{user.nickname} 退出了「{registration.tournament.title}」的临时队伍"
        f"「{registration.team_name}」，回到散人池。"
    ]
    if dissolved:
        lines.append("队伍里没有人了，已自动解散。")
    lines.append(
        f"队伍编排页：{site_url(f'/admin/tournaments/{registration.tournament_id}/teams/')}"
    )
    body = "\n\n".join(lines)
    for address in emails_for_groups([MANAGER_GROUP]):
        send_mail(
            subject="临时队伍成员退出",
            message=body,
            from_email=None,
            recipient_list=[address],
            fail_silently=False,
        )
