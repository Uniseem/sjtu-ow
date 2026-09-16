"""Team emails (design 7.3, 7.4, 7.5). All go through the queued backend."""

from __future__ import annotations

from django.conf import settings
from django.core.mail import send_mail


def site_url(path: str) -> str:
    base = getattr(settings, "SITE_URL", "") or ""
    return base.rstrip("/") + path


def _send(subject: str, body: str, recipients) -> None:
    """One message per address: recipients must not see each other's email."""
    for address in sorted({address for address in recipients if address}):
        send_mail(
            subject=subject,
            message=body,
            from_email=None,
            recipient_list=[address],
            fail_silently=False,
        )


def application_submitted(application) -> None:
    captain = application.team.captain()
    if captain is None:
        return
    roles = "、".join(application.role_labels()) or "未填"
    body = (
        f"{application.applicant.nickname} 申请加入「{application.team.name}」。\n\n"
        f"意向位置：{roles}\n"
        f"留言：{application.message or '（无）'}\n\n"
        f"去审批：{site_url(f'/teams/{application.team_id}/manage/')}"
    )
    _send("有人申请加入你的战队", body, [captain.email])


def application_decided(application) -> None:
    team = application.team
    if application.status == "approved":
        body = (
            f"你加入「{team.name}」的申请已通过。\n\n"
            f"战队主页：{site_url(team.get_absolute_url())}"
        )
        subject = "入队申请已通过"
    else:
        reason = application.decision_note or "（未填写原因）"
        body = (
            f"你加入「{team.name}」的申请没有通过。\n\n"
            f"原因：{reason}\n\n"
            f"你可以调整后再次申请：{site_url(team.get_absolute_url())}"
        )
        subject = "入队申请未通过"
    _send(subject, body, [application.applicant.email])


def member_removed(team, user) -> None:
    body = f"你已被移出战队「{team.name}」。如有疑问，请联系队长。"
    _send("你已被移出战队", body, [user.email])


def captain_changed(team, new_captain) -> None:
    body = (
        f"你已成为「{team.name}」的队长。\n\n"
        f"战队管理：{site_url(f'/teams/{team.pk}/manage/')}"
    )
    _send("你已成为战队队长", body, [new_captain.email])


def team_disbanded(team, members) -> None:
    body = f"战队「{team.name}」已解散。相关的入队申请也已取消。"
    _send("战队已解散", body, [member.email for member in members])
