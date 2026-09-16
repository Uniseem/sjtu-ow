"""Emails about the open API (design 11.8.3). Sent to superusers only.

Subjects are bare -- core.mail adds the site's configured prefix.
"""

from __future__ import annotations

import logging

from django.conf import settings
from django.core.mail import send_mail
from django.urls import reverse

logger = logging.getLogger(__name__)


def superuser_emails() -> list[str]:
    from accounts.models import User

    return sorted(
        address
        for address in User.objects.filter(
            is_active=True, is_superuser=True
        ).values_list("email", flat=True)
        if address
    )


def webhook_failed(delivery) -> None:
    """One mail per superuser after all eight attempts are used up."""
    recipients = superuser_emails()
    if not recipients:
        logger.warning("Webhook %s 投递失败，但没有超级管理员邮箱", delivery.event_id)
        return
    try:
        path = reverse("integrations_webhook_deliveries", args=[delivery.client_id])
    except Exception:  # noqa: BLE001 — the mail matters more than the link
        path = ""
    link = f"{settings.SITE_URL.rstrip('/')}{path}" if path else ""
    body = (
        f"上游「{delivery.client.name}」的 Webhook 投递失败了。\n\n"
        f"事件类型：{delivery.event_type}\n"
        f"事件 ID：{delivery.event_id}\n"
        f"尝试次数：{delivery.attempts}\n"
        f"最后状态码：{delivery.last_status_code or '（没有响应）'}\n"
        f"最后错误：{delivery.last_error or '无'}\n"
    )
    if link:
        body += f"\n在后台查看和手动重发：{link}\n"
    for address in recipients:
        send_mail(
            subject=f"Webhook 投递失败：{delivery.client.name}",
            message=body,
            from_email=None,
            recipient_list=[address],
            fail_silently=True,
        )
