"""One context for the static and the interactive comment section (13.13.3).

The prerendered article carries the read-only section. A signed-in visitor
gets the interactive one, either from the state fragment (slot
``article-comments:<page id>``) or directly when Django renders the page
live for them.
"""

from __future__ import annotations

from django.template.loader import render_to_string

from comments import services


def section_context(request, page, *, interactive: bool, page_number=None) -> dict:
    user = getattr(request, "user", None) if interactive else None
    data = services.thread(page, viewer=user, page_number=page_number or 1)
    context = {
        "page": page,
        "thread": data,
        "interactive": interactive,
        "can_moderate": services.can_moderate(user) if interactive else False,
        "post_problems": services.can_comment(user, page) if interactive else [],
    }
    context["can_post"] = interactive and not context["post_problems"]
    return context


def render_section(request, page, *, interactive: bool, oob=False, **extra) -> str:
    context = section_context(request, page, interactive=interactive)
    context["oob"] = oob
    context.update(extra)
    return render_to_string("comments/section.html", context, request=request)


def article_comments_slot(request, argument):
    """The state-fragment renderer registered in apps.py."""
    page = services.commentable_page(argument)
    if page is None:
        return ""
    return render_section(request, page, interactive=True, oob=True)
