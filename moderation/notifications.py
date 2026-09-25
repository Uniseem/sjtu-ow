"""Emails about flagged content (design 5.5.4). Sent to admins, never to authors."""

from __future__ import annotations

import logging

from django.conf import settings
from django.core.mail import send_mail
from django.urls import reverse
from django.utils import timezone

from moderation.models import ModerationItem, Risk

logger = logging.getLogger(__name__)

REVIEWER_GROUPS = ("内容编辑",)


def reviewer_emails() -> list[str]:
    """Content editors and superusers (design 5.5.4)."""
    from core.mail import emails_for_groups

    return emails_for_groups(REVIEWER_GROUPS)


def _send_one_by_one(subject: str, body: str, recipients) -> None:
    """One message per address so reviewers never see each other's email."""
    for address in recipients:
        send_mail(
            subject=subject,
            message=body,
            from_email=None,
            recipient_list=[address],
            fail_silently=False,
        )


def admin_url(item: ModerationItem) -> str:
    base = getattr(settings, "WAGTAILADMIN_BASE_URL", "") or ""
    return base.rstrip("/") + reverse("moderation_detail", args=[item.pk])


def notify_high_risk(item: ModerationItem) -> None:
    """High risk goes out immediately unless the admin chose daily summaries."""
    from core.models import SiteSettings

    try:
        mode = SiteSettings.load().moderation_high_risk_notify
    except Exception:  # noqa: BLE001
        mode = "immediate"
    if mode != "immediate":
        return
    if item.notified_at:
        return  # already mailed; a re-check must not mail again
    recipients = reviewer_emails()
    if not recipients:
        return
    body = (
        f"AI 审核标记了一条高风险内容，请到后台复核。\n\n"
        f"类型：{item.get_target_type_display()}\n"
        f"类别：{'、'.join(item.category_labels()) or '未分类'}\n"
        f"理由：{item.reason}\n"
        f"内容片段：{item.quote or item.excerpt[:200]}\n\n"
        f"复核地址：{admin_url(item)}\n\n"
        f"（AI 只做判断，不会改动任何内容。处置请在后台进行。）"
    )
    _send_one_by_one("高风险内容待复核", body, recipients)
    ModerationItem.objects.filter(pk=item.pk).update(notified_at=timezone.now())


def send_digest() -> int:
    """One summary of everything still waiting, low and medium first."""
    pending = list(
        ModerationItem.objects.filter(
            status=ModerationItem.Status.PENDING,
            notified_at__isnull=True,
            checked_at__isnull=False,
        ).exclude(risk=Risk.NONE)
    )
    if not pending:
        return 0
    recipients = reviewer_emails()
    if not recipients:
        return 0
    lines = [f"待复核内容共 {len(pending)} 条：", ""]
    for item in pending:
        lines.append(
            f"- [{item.get_risk_display()}] {item.get_target_type_display()}："
            f"{item.excerpt[:60]}　{admin_url(item)}"
        )
    lines.append("")
    lines.append("（AI 只做判断，不会改动任何内容。处置请在后台进行。）")
    _send_one_by_one("内容审核每日汇总", "\n".join(lines), recipients)
    ModerationItem.objects.filter(pk__in=[item.pk for item in pending]).update(
        notified_at=timezone.now()
    )
    return len(pending)
