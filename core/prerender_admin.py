"""Wagtail admin for the static pages (design 13.13.6)."""

from __future__ import annotations

from django.contrib import messages
from django.core.paginator import Paginator
from django.db.models import Count, Max
from django.shortcuts import redirect, render
from django.urls import reverse
from django.views.decorators.http import require_POST

from core import prerender
from core.fonts.admin_views import superuser_required
from core.models import PrerenderedPage

PER_PAGE = 50


@superuser_required
def prerender_index(request):
    counts = dict(
        PrerenderedPage.objects.values_list("status").annotate(total=Count("id"))
    )
    latest = PrerenderedPage.objects.filter(
        status=PrerenderedPage.Status.READY
    ).aggregate(latest=Max("generated_at"))["latest"]
    status = request.GET.get("status", "")
    if status not in PrerenderedPage.Status.values:
        status = ""
    records = PrerenderedPage.objects.all()
    if status:
        records = records.filter(status=status)
    page = Paginator(records, PER_PAGE).get_page(request.GET.get("page"))
    statuses = [("", "全部", sum(counts.values()))] + [
        (value, label, counts.get(value, 0))
        for value, label in PrerenderedPage.Status.choices
    ]
    return render(
        request,
        "core/prerender/index.html",
        {
            "page_title": "静态页面",
            "enabled": prerender.is_enabled(),
            "records": page,
            "status": status,
            "statuses": statuses,
            "ready_count": counts.get(PrerenderedPage.Status.READY, 0),
            "failed_count": counts.get(PrerenderedPage.Status.FAILED, 0),
            "latest": latest,
            "disk_bytes": prerender.disk_usage(),
            "root": str(prerender.root()),
            "breadcrumbs_items": [
                {"url": reverse("backoffice:home"), "label": "首页"},
                {"url": "", "label": "静态页面"},
            ],
        },
    )


@superuser_required
@require_POST
def prerender_rebuild(request):
    path = request.POST.get("path", "").strip()
    if not prerender.is_enabled():
        messages.error(request, "预渲染当前是关闭的（PRERENDER_ENABLED）。")
    elif path:
        prerender.request_page(path)
        messages.success(request, f"已排入队列：{path}")
    else:
        prerender.request_all()
        messages.success(request, "已排入队列：全部页面。")
    return redirect("core_prerender_index")


@superuser_required
@require_POST
def prerender_clear(request):
    count = prerender.clear_all()
    messages.success(
        request,
        f"已清空静态文件（{count} 个页面记录保留，状态改为等待生成）。"
        "网站会自动回落到实时渲染。",
    )
    return redirect("core_prerender_index")
