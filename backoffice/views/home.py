"""后台首页 (docs/admin.md 4.1): hello, the to-do, one's articles, the setup list."""

from __future__ import annotations

from django.shortcuts import render

from backoffice.nav import placed


def _my_articles(user):
    from backoffice.views.articles import article_status
    from content.models import ArticlePage

    pages = (
        ArticlePage.objects.filter(owner=user)
        .annotate_approved_schedule()
        .select_related("category")
        .order_by("-latest_revision_created_at", "-pk")[:5]
    )
    return [(page, article_status(page)) for page in pages]


@placed("home", "home")
def home(request):
    from core.admin_home import actions, roles
    from core.admin_todo import has_duties, todo_rows

    user = request.user
    context = {
        "page_title": "首页",
        "nickname": getattr(user, "nickname", "") or user.get_username(),
        "roles": roles(user),
        "actions": actions(user),
        "has_duties": has_duties(user),
        "todo": todo_rows(user) if has_duties(user) else [],
        "articles": _my_articles(user),
    }
    if user.is_superuser:
        from core.admin_setup import setup_checks

        checks = setup_checks()
        context["setup"] = {
            "required": [c for c in checks if c.required and not c.done],
            "optional": [c for c in checks if not c.required and not c.done],
            "done": [c for c in checks if c.done],
        }
    return render(request, "backoffice/home.html", context)
