"""Wagtail admin for the static pages (design 13.13.6)."""

from __future__ import annotations

from django.contrib import messages
from django.shortcuts import redirect, render
from django.urls import reverse
from django.views.decorators.http import require_POST

from core import prerender
from core.fonts.admin_views import superuser_required
from core.models import PrerenderedPage


@superuser_required
def prerender_index(request):
    records = list(PrerenderedPage.objects.all())
    failed = [item for item in records if item.status == PrerenderedPage.Status.FAILED]
    ready = [item for item in records if item.status == PrerenderedPage.Status.READY]
    latest = max(
        (item.generated_at for item in ready if item.generated_at),
        default=None,
    )
    return render(
        request,
        "core/prerender/index.html",
        {
            "page_title": "静态页面",
            "header_icon": "doc-full",
            "enabled": prerender.is_enabled(),
            "records": records,
            "ready_count": len(ready),
            "failed": failed,
            "latest": latest,
            "disk_bytes": prerender.disk_usage(),
            "root": str(prerender.root()),
            "breadcrumbs_items": [
                {"url": reverse("wagtailadmin_home"), "label": "首页"},
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
