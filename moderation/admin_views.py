"""Wagtail admin review queue (design 5.5.4).

Every action here is performed by a human; the AI never gets a button.
"""

from __future__ import annotations

from datetime import timedelta
from functools import wraps

from django.contrib import messages
from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.core.exceptions import PermissionDenied
from django.core.paginator import Paginator
from django.db import transaction
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone
from django.views.decorators.http import require_POST
from wagtail.log_actions import log as wagtail_log
from wagtail.models import ModelLogEntry

from moderation import services
from moderation.models import Category, ModerationItem, Risk, TargetType
from moderation.tasks import (
    SCAN_LOCK_KEY,
    SCAN_LOCK_SECONDS,
    scan_existing_content,
    scan_start,
)

PAGE_SIZE = 25
ACTIONS = {
    "ok": (ModerationItem.Status.OK, "标记为无问题"),
    "handled": (ModerationItem.Status.HANDLED, "已处置"),
    "ignored": (ModerationItem.Status.IGNORED, "忽略"),
}
# Every handling goes into Wagtail's action log, so the next one does not
# overwrite who did what (design 5.5.4, round 118).
HANDLE_LOG_ACTION = "moderation.handle"
# The list's time filter (design 5.5.4): value -> (label, days).
SINCE = {
    "1": ("最近 24 小时", 1),
    "7": ("最近 7 天", 7),
    "30": ("最近 30 天", 30),
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
    since = request.GET.get("since", "")
    if since not in SINCE:
        since = ""

    queryset = ModerationItem.objects.select_related("author").exclude(risk=Risk.NONE)
    if since:
        queryset = queryset.filter(
            created_at__gte=timezone.now() - timedelta(days=SINCE[since][1])
        )
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
            "since": since,
            "since_choices": [
                (value, label) for value, (label, _days) in SINCE.items()
            ],
            "scan_running": cache.get(SCAN_LOCK_KEY) is not None,
            "statuses": ModerationItem.Status.choices,
            "risks": Risk.choices,
            "target_types": TargetType.choices,
            "enabled": services.is_enabled(),
            "disabled_reason": services.disabled_reason(),
            "configured": services.is_configured(),
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
            "author_problem": services.author_problem(item),
            "revise_max": services.REVISE_MAX_CHARS,
            "history": ModelLogEntry.objects.for_instance(item)
            .filter(action__in=[HANDLE_LOG_ACTION, services.REVISE_LOG_ACTION])
            .select_related("user")
            .order_by("-timestamp"),
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
    if request.POST.get("clear_motto") and item.target_type == TargetType.MOTTO:
        # The one thing a reviewer can change here: a motto is a line of
        # text with no other editing screen (design-details 3.1).
        User = get_user_model()
        User.objects.filter(pk=item.target_id).update(motto="")
        owner = User.objects.filter(pk=item.target_id).first()
        if owner is not None:
            from accounts.services import refresh_nickname_pages

            refresh_nickname_pages(owner)
        label += "，并清空了这条个人宣言"
    item.status = status
    item.handling_note = request.POST.get("handling_note", "")[:300]
    item.reviewed_by = request.user
    item.reviewed_at = timezone.now()
    item.save(update_fields=["status", "handling_note", "reviewed_by", "reviewed_at"])
    wagtail_log(
        instance=item,
        action=HANDLE_LOG_ACTION,
        user=request.user,
        data={"result": label, "note": item.handling_note},
    )
    untouched = "" if "清空" in label else "内容本身没有被改动。"
    messages.success(request, f"已记录：{label}。{untouched}")
    return redirect("moderation_index")


@reviewer_required
@require_POST
def moderation_scan(request):
    """「全量扫描」 (design 5.5.4): queue every existing piece of content in
    the background, in the off-peak hours (5.5.3). One at a time; repeats
    are cheap because text already on record is not sent again."""
    now = timezone.now()
    start = scan_start(now)
    wait = max(0, int((start - now).total_seconds()))
    if not services.is_enabled():
        messages.error(request, "AI 审核当前是关闭的，没有发起扫描。")
    elif not cache.add(SCAN_LOCK_KEY, request.user.pk, wait + SCAN_LOCK_SECONDS):
        messages.warning(request, "全量扫描已经排上或正在进行，稍后刷新列表看结果。")
    else:
        transaction.on_commit(
            lambda: scan_existing_content.using(run_after=start).enqueue()
        )
        when = "现在就开始"
        if wait >= 60:
            moment = timezone.localtime(start)
            when = f"将在 {moment:%m 月 %d 日 %H:%M} 开始（夜间价格低一半）"
        messages.success(
            request,
            f"全量扫描{when}：昵称、个人宣言、文章和页面、战队、评论都会送审，"
            "在后台进行，结果陆续出现在列表里。送过的内容不会重复送，每日上限照常。",
        )
    return redirect("moderation_index")


@reviewer_required
@require_POST
def moderation_ask_author(request, pk):
    """「要求作者修改」: the one direct action on this page (v6.17)."""
    item = get_object_or_404(ModerationItem.objects.select_related("author"), pk=pk)
    try:
        services.ask_author_to_revise(
            item=item, actor=request.user, message=request.POST.get("message", "")
        )
    except services.ModerationError as exc:
        messages.error(request, str(exc))
        return redirect("moderation_detail", pk=pk)
    messages.success(
        request,
        f"已发信给 {item.author.nickname}，请其修改。"
        "这条记为「已处置」，内容本身没有被改动。",
    )
    return redirect("moderation_detail", pk=pk)


@reviewer_required
@require_POST
def moderation_try(request):
    """「试一下」 (round 122): one sample through the AI, to check the key."""
    ok, message = services.try_connection()
    (messages.success if ok else messages.error)(request, message)
    return redirect("moderation_index")
