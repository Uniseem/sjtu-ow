"""Admin review of uploaded faces (design-details 2.3, design 14.2; v6.11).

Content editors and superusers, the same people as the content review queue
(design 5.5.4). Every decision goes through accounts.services, which keeps
the pictures, the faces and the emails in step.
"""

from __future__ import annotations

from django.contrib import messages
from django.core.paginator import Paginator
from django.db.models import Count, Q
from django.shortcuts import redirect, render
from django.urls import reverse
from django.utils.http import url_has_allowed_host_and_scheme
from django.views.decorators.http import require_POST

from accounts import services
from accounts.models import AvatarSubmission
from moderation.admin_views import _breadcrumbs, reviewer_required
from moderation.models import Category

PAGE_SIZE = 24
# v6.73: uploads show at once, so the page lists the faces in use (newest
# first) to take down; 未通过 is what was refused before v6.73.
TABS = (
    AvatarSubmission.Status.APPROVED,
    AvatarSubmission.Status.TAKEN_DOWN,
    AvatarSubmission.Status.REJECTED,
)


@reviewer_required
def avatar_review(request):
    status = request.GET.get("status", AvatarSubmission.Status.APPROVED)
    if status not in TABS:
        status = AvatarSubmission.Status.APPROVED
    queryset = (
        AvatarSubmission.objects.filter(status=status)
        .select_related("user", "user__avatar", "image", "reviewed_by")
        .prefetch_related("image__renditions")
        .annotate(
            turned_down=Count(
                "user__avatar_submissions",
                filter=Q(
                    user__avatar_submissions__status__in=[
                        AvatarSubmission.Status.REJECTED,
                        AvatarSubmission.Status.TAKEN_DOWN,
                    ]
                ),
            )
        )
        .order_by("-created_at", "-pk")
    )
    page = Paginator(queryset, PAGE_SIZE).get_page(request.GET.get("page"))
    counts = dict(
        AvatarSubmission.objects.filter(status__in=TABS)
        .values_list("status")
        .annotate(n=Count("pk"))
        .values_list("status", "n")
    )
    tabs = [
        (value, AvatarSubmission.Status(value).label, counts.get(value, 0))
        for value in TABS
    ]
    return render(
        request,
        "moderation/avatars.html",
        {
            "page_title": "头像",
            "items": page,
            "status": status,
            "status_label": AvatarSubmission.Status(status).label,
            "tabs": tabs,
            "reasons": Category.choices,
            "breadcrumbs_items": _breadcrumbs({"url": "", "label": "头像"}),
        },
    )


@reviewer_required
@require_POST
def avatar_review_action(request, pk):
    action = request.POST.get("action", "")
    reason = request.POST.get("reason", "")
    note = request.POST.get("note", "")
    back = request.POST.get("next", "")
    if not url_has_allowed_host_and_scheme(back, allowed_hosts={request.get_host()}):
        back = reverse("avatar_review")
    try:
        if action == "take_down":
            submission = services.take_down_avatar(pk, request.user, reason, note)
            who = submission.user.nickname
            messages.success(request, f"已撤下，{who} 现在用默认头像，已发信说明原因。")
        else:
            messages.error(request, "未知的处理方式。")
    except services.AvatarReviewError as error:
        messages.error(request, str(error))
    return redirect(back)
