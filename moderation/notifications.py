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
from moderation.models import ModerationItem

logger = logging.getLogger(__name__)

REVIEWER_GROUPS = ("内容编辑",)
PATROL_NOTE = (
    "网站默认信任所有人，没有自动隐藏或撤下任何内容。AI 只做判断，可能看错；"
    "要不要处理、怎么处理，由你在后台决定。"
)
PATROL_WHY = (
    "你收到这封邮件，是因为全站设置里的「巡查提醒发到」填的是你，或者你是超级管理员。"
)


def reviewer_emails() -> list[str]:
    """Content editors and superusers (design 5.5.4)."""
    from core.mail import emails_for_groups

    return emails_for_groups(REVIEWER_GROUPS)


def admin_url(item: ModerationItem) -> str:
    base = getattr(settings, "WAGTAILADMIN_BASE_URL", "") or ""
    return base.rstrip("/") + reverse("moderation_detail", args=[item.pk])


def index_url() -> str:
    base = getattr(settings, "WAGTAILADMIN_BASE_URL", "") or ""
    return base.rstrip("/") + reverse("moderation_index")


def alert_recipients() -> list[str]:
    """「巡查提醒发到」 in 全站设置, or every active superuser (5.5.4, v6.72)."""
    from django.contrib.auth import get_user_model

    from core.models import SiteSettings

    address = (SiteSettings.load().moderation_alert_email or "").strip()
    if address:
        return [address]
    return sorted(
        set(
            get_user_model()
            .objects.filter(is_active=True, is_superuser=True)
            .exclude(email="")
            .values_list("email", flat=True)
        )
    )


def _content_url(item) -> str:
    from core.letters import site_url

    if not item.url:
        return admin_url(item)
    return site_url(item.url) if item.url.startswith("/") else item.url


def patrol_letter(items) -> Letter:
    count = len(items)
    return Letter(
        subject=f"AI 巡查发现 {count} 条可能不妥的内容",
        lead=f"这次巡查有 {count} 条内容 AI 觉得可能不妥，逐条列在下面。",
        items=[
            (
                f"[{item.get_risk_display()}] {item.get_target_type_display()}"
                f"（{'、'.join(item.category_labels()) or '未分类'}）："
                f"{(item.quote or item.excerpt)[:80]}（AI 的理由：{item.reason[:80]}）",
                _content_url(item),
            )
            for item in items
        ],
        item_link="看内容",
        action=("到后台看巡查记录", index_url()),
        note=PATROL_NOTE,
        reason=PATROL_WHY,
    )


def send_patrol_alert() -> int:
    """One letter for everything this patrol found doubtful that nobody has
    been told about yet; nothing found, nothing sent. Returns how many."""
    from moderation.patrol import doubtful_unsent

    items = list(doubtful_unsent())
    if not items:
        return 0
    recipients = alert_recipients()
    if not recipients:
        logger.warning("AI 巡查发现 %s 条可疑内容，但没有收件人", len(items))
        return 0
    send(patrol_letter(items), recipients)
    ModerationItem.objects.filter(pk__in=[item.pk for item in items]).update(
        notified_at=timezone.now()
    )
    return len(items)


# --- asking the author to change something (design 5.5.4, v6.17) ------------

# What the subject calls each kind of content.
REVISE_NOUN = {
    "article": "文章",
    "page": "页面",
}
REVISE_WHY = "你收到这封邮件，是因为你在社区发布的内容需要修改。"


def revise_url(item) -> str:
    """Where the author changes this piece; "" when there is nowhere to send them."""
    from core.letters import site_url

    admin = (getattr(settings, "WAGTAILADMIN_BASE_URL", "") or "").rstrip("/")
    kind = item.target_type
    if kind in ("nickname", "motto"):
        return site_url(reverse("me_profile"))
    if kind in ("team_name", "team_description"):
        return site_url(reverse("team_manage", args=[item.target_id]))
    if kind == "application_message":
        return site_url(reverse("me_teams"))
    if kind == "article":
        return admin + reverse("backoffice:article_edit", args=[item.target_id])
    if kind == "page":
        return admin + reverse("backoffice:page_edit", args=[item.target_id])
    if kind == "tournament_description":
        return admin + reverse("tournaments:edit", args=[item.target_id])
    if kind == "scrim_description":
        return admin + reverse("scrims:edit", args=[item.target_id])
    if kind == "comment" and item.url:
        return site_url(item.url) if item.url.startswith("/") else item.url
    return ""


def revise_letter(item, message: str, before: int = 0) -> Letter:
    """``before``: how many were sent about this item already (v7.5)."""
    kind = item.get_target_type_display()
    noun = REVISE_NOUN.get(item.target_type, kind)
    facts = [("内容类型", kind), ("内容片段", (item.quote or item.excerpt)[:200])]
    link = revise_url(item)
    notice = (
        f"关于这条{noun}，之前已经发过 {before} 次修改提醒，"
        "这次可能有修改，请以这封为准。"
        if before
        else ""
    )
    return Letter(
        subject=f"请修改你的{noun}",
        lead=f"社区的管理员看过你发布的一条{noun}，请你按下面的说明修改。",
        facts=facts,
        paragraphs=[f"管理员的说明：{message}", "改完保存就行，不用回复这封邮件。"],
        action=("去修改", link) if link else None,
        reason=REVISE_WHY,
        notice=notice,
    )


def ask_author(item, message: str, before: int = 0) -> None:
    send(revise_letter(item, message, before), [item.author])
