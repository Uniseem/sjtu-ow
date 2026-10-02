"""Emails about flagged content (design 5.5.4). Sent to admins, never to authors.

Written as letters (10.3): ``*_letter`` builds what an email says; the
function that sends it lives next to it (see teams.notifications).
"""

from __future__ import annotations

import logging

from django.conf import settings
from django.urls import reverse
from django.utils import timezone

from core.letters import Letter, send
from moderation.models import ModerationItem, Risk

logger = logging.getLogger(__name__)

REVIEWER_GROUPS = ("内容编辑",)
AI_NOTE = "AI 只做判断，不会改动任何内容。处置请在后台进行。"
WHY = "你收到这封邮件，是因为你是内容编辑或超级管理员。"


def reviewer_emails() -> list[str]:
    """Content editors and superusers (design 5.5.4)."""
    from core.mail import emails_for_groups

    return emails_for_groups(REVIEWER_GROUPS)


def admin_url(item: ModerationItem) -> str:
    base = getattr(settings, "WAGTAILADMIN_BASE_URL", "") or ""
    return base.rstrip("/") + reverse("moderation_detail", args=[item.pk])


def high_risk_letter(item) -> Letter:
    kind = item.get_target_type_display()
    return Letter(
        subject=f"高风险内容待复核：{kind}",
        lead="AI 审核标记了一条高风险内容，请到后台复核。",
        facts=[
            ("类型", kind),
            ("类别", "、".join(item.category_labels()) or "未分类"),
            ("理由", item.reason),
            ("内容片段", item.quote or item.excerpt[:200]),
        ],
        action=("去后台复核", admin_url(item)),
        note=AI_NOTE,
        reason=WHY,
    )


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
    send(high_risk_letter(item), recipients)
    ModerationItem.objects.filter(pk=item.pk).update(notified_at=timezone.now())


def digest_letter(pending) -> Letter:
    return Letter(
        subject=f"内容审核每日汇总：{len(pending)} 条待复核",
        lead=f"有 {len(pending)} 条内容在等复核，逐条列在下面。",
        items=[
            (
                f"[{item.get_risk_display()}] {item.get_target_type_display()}："
                f"{item.excerpt[:60]}",
                admin_url(item),
            )
            for item in pending
        ],
        item_link="去复核",
        note=AI_NOTE,
        reason=WHY,
    )


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
    send(digest_letter(pending), recipients)
    ModerationItem.objects.filter(pk__in=[item.pk for item in pending]).update(
        notified_at=timezone.now()
    )
    return len(pending)
