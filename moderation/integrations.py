"""Where content enters the review queue (design 5.5.1)."""

from __future__ import annotations

from django.utils.html import strip_tags

from moderation import services
from moderation.models import TargetType

PAGE_TYPES = {
    "ArticlePage": TargetType.ARTICLE,
    "StandardPage": TargetType.PAGE,
}


def page_target_type(page) -> str:
    return PAGE_TYPES.get(type(page.specific).__name__, "")


def page_text(page) -> str:
    """Title, summary and body as plain text; nothing about the author."""
    specific = page.specific
    parts = [specific.title]
    summary = getattr(specific, "summary", "")
    if summary:
        parts.append(summary)
    body = getattr(specific, "body", None)
    if body is not None:
        parts.append(strip_tags(str(body)))
    return "\n\n".join(part for part in parts if part).strip()


def submit_page(page):
    target_type = page_target_type(page)
    if not target_type:
        return None
    specific = page.specific
    author = getattr(specific, "author", None) or specific.owner
    return services.submit(
        target_type=target_type,
        target_id=specific.pk,
        field="content",
        text=page_text(specific),
        url=specific.get_url() or "",
        author=author,
    )


def submit_nickname(user):
    return services.submit(
        target_type=TargetType.NICKNAME,
        target_id=user.pk,
        field="nickname",
        text=user.nickname or "",
        url="",
        author=user,
    )
