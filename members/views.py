from django.http import Http404
from django.shortcuts import render
from django.views.decorators.http import require_GET

from members.services import joined_users, member_page, showcase


@require_GET
def members_index(request):
    """Public member showcase (design 6.3)."""
    return render(request, "members/index.html", showcase())


@require_GET
def member_detail(request, pk):
    """A member's own page (design 6.4). Only people on the showcase have one;
    rendered live and kept out of search engines until its design is settled."""
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
