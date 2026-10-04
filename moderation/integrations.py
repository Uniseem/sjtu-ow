"""Where content enters the review queue (design 5.5.1)."""

from __future__ import annotations

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
    if body:
        # Markdown (v6.70): sent as written, link addresses included.
        parts.append(str(body))
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


def submit_motto(user):
    """The one-line motto on the member page (design-details 3.1, v5.2)."""
    if not user.motto:
        return None
    return services.submit(
        target_type=TargetType.MOTTO,
        target_id=user.pk,
        field="motto",
        text=user.motto,
        url="/members/",
        author=user,
    )


def submit_team(team) -> int:
    """Name and introduction, as teams.services.on_team_changed sends them
    (without its page refreshes). Returns how many went in."""
    author = team.captain()
    sent = 0
    for target_type, field, text in (
        (TargetType.TEAM_NAME, "name", team.name),
        (TargetType.TEAM_DESCRIPTION, "description", team.description),
    ):
        if not text:
            continue
        if (
            services.submit(
                target_type=target_type,
                target_id=team.pk,
                field=field,
                text=text,
                url=team.get_absolute_url(),
                author=author,
            )
            is not None
        ):
            sent += 1
    return sent


def submit_comment(comment):
    """As comments.services sends a new or edited comment (design 5.6)."""
    page = comment.page
    return services.submit(
        target_type=TargetType.COMMENT,
        target_id=comment.pk,
        field="body",
        text=comment.body,
        url=f"{page.get_url() or ''}#{comment.anchor}",
        author=comment.author,
    )


SCAN_KINDS = ("nicknames", "pages", "teams", "comments")


def scan_existing(what: str = "all", limit: int = 0) -> int:
    """Send existing content through review (design 5.5.4 全量扫描): every
    active member's nickname and motto, live articles and pages, standing
    teams, visible comments. Text already on record is not sent again and
    the daily limit holds, so running it twice costs nothing extra. Returns
    how many pieces went in, counting ones already on record."""
    from accounts.models import User
    from comments.models import Comment
    from content.models import ArticlePage, StandardPage
    from teams.models import Team

    kinds = SCAN_KINDS if what == "all" else (what,)
    submitted = 0

    def room() -> bool:
        return not limit or submitted < limit

    if "nicknames" in kinds:
        for user in User.objects.filter(is_active=True).order_by("pk"):
            if not room():
                break
            if submit_nickname(user) is not None:
                submitted += 1
            if submit_motto(user) is not None:
                submitted += 1
    if "pages" in kinds:
        for model in (ArticlePage, StandardPage):
            for page in model.objects.live().order_by("pk"):
                if not room():
                    break
                if submit_page(page) is not None:
                    submitted += 1
    if "teams" in kinds:
        for team in Team.objects.filter(disbanded_at__isnull=True).order_by("pk"):
            if not room():
                break
            submitted += submit_team(team)
    if "comments" in kinds:
        visible = Comment.objects.filter(is_hidden=False, is_deleted=False)
        for comment in visible.select_related("page", "author").order_by("pk"):
            if not room():
                break
            if submit_comment(comment) is not None:
                submitted += 1
    return submitted
