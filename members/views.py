from django.http import Http404
from django.shortcuts import render
from django.views.decorators.http import require_GET

from members.services import joined_users, looking_for, member_page, showcase


@require_GET
def members_index(request):
    """Public member showcase (design 6.3); filtered views (v6.40) are live."""
    from accounts.roles import ROLE_CHOICES

    context = showcase()
    labels = dict(ROLE_CHOICES)
    role = request.GET.get("role", "")
    role = role if role in labels else ""
    free = request.GET.get("free") == "1"
    filtering = bool(role or free)
    context.update(
        {
            "role": role,
            "free": free,
            "filtering": filtering,
            "role_choices": ROLE_CHOICES,
            "shown": looking_for(context["members"], role=role, free=free)
            if filtering
            else context["members"],
        }
    )
    return render(request, "members/index.html", context)


@require_GET
def member_detail(request, pk):
    """A member's own page (design 6.4). Only people on the showcase have one;
    rendered live and kept out of search engines (v6.41 kept it that way)."""
    user = joined_users().filter(pk=pk).prefetch_related("game_accounts").first()
    if user is None:
        raise Http404("没有这位成员。")
    return render(
        request,
        "members/detail.html",
        {
            "page": member_page(user),
            # Design 6.4 (v6.21): the owner gets a way back to 个人中心.
            "is_owner": request.user.is_authenticated and request.user.pk == user.pk,
        },
    )
