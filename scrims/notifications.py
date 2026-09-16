"""Scrim emails (design 9.1, 10.2). One message per recipient.

Subjects are written bare: core.mail prefixes every outgoing message with
the site's configured prefix ([SJTU OW] by default, 附录 C), so a prefix
written here would be doubled and would ignore the admin's setting.
"""

from __future__ import annotations

import logging

from django.core.mail import send_mail
from django.urls import reverse
from django.utils import timezone

from tournaments.notifications import site_url

logger = logging.getLogger(__name__)


def _when(scrim) -> str:
    return timezone.localtime(scrim.starts_at).strftime("%Y-%m-%d %H:%M")


def _link(scrim) -> str:
    return site_url(reverse("scrim_detail", args=[scrim.pk]))


def _recipients(scrim) -> list[str]:
    return sorted(
        {
            signup.user.email
            for signup in scrim.signups.select_related("user")
            if signup.user.is_active and signup.user.email
        }
    )


def _send(recipients, subject, body) -> int:
    sent = 0
    for address in recipients:
        send_mail(
            subject=subject,
            message=body,
            from_email=None,
            recipient_list=[address],
            fail_silently=True,
        )
        sent += 1
    return sent


def scrim_cancelled(scrim) -> int:
    """Design 9.1: tell everyone who signed up."""
    body = (
        f"内战「{scrim.title}」已取消。\n\n"
        f"原定时间：{_when(scrim)}\n"
        f"规格：{scrim.get_format_display()}\n\n"
        f"活动页面：{_link(scrim)}\n"
    )
    return _send(_recipients(scrim), f"内战已取消：{scrim.title}", body)


def scrim_reminder(scrim) -> int:
    """Design 9.1: the reminder that goes out before it starts."""
    body = (
        f"内战「{scrim.title}」就要开始了。\n\n"
        f"开始时间：{_when(scrim)}\n"
        f"规格：{scrim.get_format_display()}\n\n"
        f"活动页面：{_link(scrim)}\n"
    )
    return _send(_recipients(scrim), f"内战提醒：{scrim.title}", body)
