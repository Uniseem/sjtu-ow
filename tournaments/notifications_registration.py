"""Registration emails (design 10.2). One message per recipient."""

from __future__ import annotations

from django.core.mail import send_mail

from tournaments.models import RegistrationAction, RegistrationStatus
from tournaments.notifications import site_url

SUBMIT_SUBJECTS = {
    RegistrationAction.SUBMIT: "报名已提交",
    RegistrationAction.RESUBMIT: "报名已重新提交",
    RegistrationAction.SYNC_ROSTER: "报名名单已同步",
}


def _captain(registration):
    return registration.team.captain()


def registration_submitted(registration, action) -> None:
    captain = _captain(registration)
    if captain is None or not captain.email:
        return
    subject = SUBMIT_SUBJECTS.get(action, "报名已提交")
    body = (
        f"「{registration.team_name}」报名「{registration.tournament.title}」"
        f"的名单已提交，当前状态：{registration.get_status_display()}。\n\n"
        f"名单版本：{registration.roster_version}\n"
        f"报名详情：{site_url(registration.get_absolute_url())}"
    )
    send_mail(
        subject=subject,
        message=body,
        from_email=None,
        recipient_list=[captain.email],
        fail_silently=False,
    )


def registration_status_changed(registration, note="") -> None:
    captain = _captain(registration)
    if captain is None or not captain.email:
        return
    label = registration.get_status_display()
    lines = [
        f"「{registration.team_name}」报名「{registration.tournament.title}」"
        f"的状态变成了：{label}。",
    ]
    if note:
        lines.append(f"备注：{note}")
    if registration.status == RegistrationStatus.REJECTED:
        lines.append("你可以修改后重新提交（报名截止前）。")
    lines.append(f"报名详情：{site_url(registration.get_absolute_url())}")
    send_mail(
        subject="报名状态有更新",
        message="\n\n".join(lines),
        from_email=None,
        recipient_list=[captain.email],
        fail_silently=False,
    )
