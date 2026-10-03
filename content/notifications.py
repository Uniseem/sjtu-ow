"""Article emails (design 10.4, v6.23), written as letters (10.3)."""

from __future__ import annotations

from core.letters import Letter, site_url

ANNOUNCE_WHY = "你收到这封邮件，是因为你在社区开着「活动通知」。"


def new_article_letter(page, unsubscribe: str = "") -> Letter:
    """「通知全体成员」 for a published article: 「公告：秋季招新」."""
    category = getattr(page, "category", None)
    kind = category.name if category else "文章"
    return Letter(
        subject=f"{kind}：{page.title}",
        lead=f"社团发布了一篇{kind}「{page.title}」。",
        paragraphs=[page.summary] if getattr(page, "summary", "") else [],
        action=("阅读全文", site_url(page.url or "/")),
        reason=ANNOUNCE_WHY,
        unsubscribe=unsubscribe,
    )
