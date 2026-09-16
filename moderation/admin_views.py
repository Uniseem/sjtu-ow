"""Wagtail admin review queue (design 5.5.4).

Every action here is performed by a human; the AI never gets a button.
"""

from __future__ import annotations

from functools import wraps

from django.contrib import messages
from django.core.exceptions import PermissionDenied
from django.core.paginator import Paginator
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone
from django.views.decorators.http import require_POST

from moderation import services
from moderation.models import Category, ModerationItem, Risk, TargetType

PAGE_SIZE = 25
ACTIONS = {
    "ok": (ModerationItem.Status.OK, "标记为无问题"),
    "handled": (ModerationItem.Status.HANDLED, "已处置"),
    "ignored": (ModerationItem.Status.IGNORED, "忽略"),
}


def can_review(user) -> bool:
    return bool(
        getattr(user, "is_superuser", False)
        or user.has_perm("moderation.change_moderationitem")
    )


def reviewer_required(view):
    @wraps(view)
    def wrapper(request, *args, **kwargs):
        if not can_review(request.user):
            raise PermissionDenied("需要内容审核权限。")
        return view(request, *args, **kwargs)

    return wrapper


def _breadcrumbs(*items):
    crumbs = [{"url": reverse("wagtailadmin_home"), "label": "首页"}]
    crumbs.extend(items)
    return crumbs


@reviewer_required
def moderation_index(request):
    status = request.GET.get("status", ModerationItem.Status.PENDING)
    risk = request.GET.get("risk", "")
    target_type = request.GET.get("target_type", "")

    queryset = ModerationItem.objects.select_related("author").exclude(risk=Risk.NONE)
    if status:
        queryset = queryset.filter(status=status)
    if status == ModerationItem.Status.PENDING:
        queryset = queryset.filter(checked_at__isnull=False)
    if risk:
        queryset = queryset.filter(risk=risk)
    if target_type:
        queryset = queryset.filter(target_type=target_type)

    page = Paginator(queryset, PAGE_SIZE).get_page(request.GET.get("page"))
    usage = services.used_today()
    month = services.month_usage()
    return render(
        request,
        "moderation/index.html",
        {
            "page_title": "内容审核",
            "header_icon": "view",
            "items": page,
            "status": status,
            "risk": risk,
            "target_type": target_type,
            "statuses": ModerationItem.Status.choices,
            "risks": Risk.choices,
            "target_types": TargetType.choices,
            "enabled": services.is_enabled(),
            "model": services.current_model(),
            "usage": usage,
            "quota_left": services.quota_left(),
            "month": month,
            "breadcrumbs_items": _breadcrumbs({"url": "", "label": "内容审核"}),
        },
    )


@reviewer_required
def moderation_detail(request, pk):
    item = get_object_or_404(
        ModerationItem.objects.select_related("author", "reviewed_by"), pk=pk
    )
    author_flags = 0
    if item.author_id:
        author_flags = (
            ModerationItem.objects.filter(author_id=item.author_id)
            .exclude(pk=item.pk)
            .exclude(risk=Risk.NONE)
            .count()
        )
    return render(
        request,
        "moderation/detail.html",
        {
            "page_title": "复核内容",
            "header_icon": "view",
            "item": item,
            "categories": item.category_labels(),
            "author_flags": author_flags,
            "actions": ACTIONS,
            "all_categories": dict(Category.choices),
            "breadcrumbs_items": _breadcrumbs(
                {"url": reverse("moderation_index"), "label": "内容审核"},
                {"url": "", "label": f"#{item.pk}"},
            ),
        },
    )


@reviewer_required
@require_POST
def moderation_action(request, pk):
    item = get_object_or_404(ModerationItem, pk=pk)
    action = request.POST.get("action", "")
    if action not in ACTIONS:
        messages.error(request, "未知的处理方式。")
        return redirect("moderation_detail", pk=pk)
    status, label = ACTIONS[action]
    item.status = status
    item.handling_note = request.POST.get("handling_note", "")[:300]
    item.reviewed_by = request.user
    item.reviewed_at = timezone.now()
    item.save(update_fields=["status", "handling_note", "reviewed_by", "reviewed_at"])
    messages.success(request, f"已记录：{label}。内容本身没有被改动。")
    return redirect("moderation_index")
