"""API client administration (design 14.2). Superusers only."""

from functools import wraps

from django.contrib import messages
from django.core.exceptions import PermissionDenied
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import path, reverse
from wagtail import hooks
from wagtail.admin.menu import MenuItem

from integrations import services
from integrations.models import ApiClient, ApiRequestLog, Include, Scope

LOG_PAGE_SIZE = 50


def superuser_required(view):
    @wraps(view)
    def wrapper(request, *args, **kwargs):
        if not request.user.is_superuser:
            raise PermissionDenied("API 客户端仅限超级管理员管理。")
        return view(request, *args, **kwargs)

    return wrapper


def _breadcrumbs(*items):
    crumbs = [{"url": reverse("wagtailadmin_home"), "label": "首页"}]
    crumbs.extend(items)
    return crumbs


@superuser_required
def client_index(request):
    return render(
        request,
        "integrations/index.html",
        {
            "page_title": "API 客户端",
            "header_icon": "link",
            "clients": ApiClient.objects.all(),
            "new_secret": request.session.pop("api_new_secret", None),
            "new_secret_client": request.session.pop("api_new_secret_client", None),
            "breadcrumbs_items": _breadcrumbs({"url": "", "label": "API 客户端"}),
        },
    )


@superuser_required
def client_create(request):
    if request.method == "POST":
        name = request.POST.get("name", "").strip()
        scopes = request.POST.getlist("scopes")
        includes = request.POST.getlist("allowed_includes")
        rate = request.POST.get("rate_limit_per_minute") or 600
        if not name:
            messages.error(request, "请填写上游名称。")
        else:
            client, secret = services.create_client(
                name=name,
                scopes=scopes,
                allowed_includes=includes,
                rate_limit_per_minute=int(rate),
            )
            # Shown once on the next page, then dropped from the session.
            request.session["api_new_secret"] = secret
            request.session["api_new_secret_client"] = client.key_id
            messages.success(request, f"已创建「{client.name}」。")
            return redirect("api_client_index")
    return render(
        request,
        "integrations/create.html",
        {
            "page_title": "新建 API 客户端",
            "header_icon": "plus",
            "scopes": Scope.choices,
            "includes": Include.choices,
            "breadcrumbs_items": _breadcrumbs(
                {"url": reverse("api_client_index"), "label": "API 客户端"},
                {"url": "", "label": "新建"},
            ),
        },
    )


@superuser_required
def client_detail(request, pk):
    client = get_object_or_404(ApiClient, pk=pk)
    if request.method == "POST":
        action = request.POST.get("action")
        if action == "regenerate":
            secret = services.regenerate_secret(client)
            request.session["api_new_secret"] = secret
            request.session["api_new_secret_client"] = client.key_id
            messages.success(request, "已重新生成密钥，旧密钥立即失效。")
            return redirect("api_client_index")
        if action == "revoke":
            services.revoke(client)
            messages.success(request, f"已吊销「{client.name}」。")
            return redirect("api_client_index")
        if action == "toggle":
            client.is_active = not client.is_active
            client.save(update_fields=["is_active"])
            messages.success(request, "已启用。" if client.is_active else "已停用。")
            return redirect("api_client_detail", pk=client.pk)
    return render(
        request,
        "integrations/detail.html",
        {
            "page_title": client.name,
            "header_icon": "link",
            "client": client,
            "logs": ApiRequestLog.objects.filter(client=client)[:LOG_PAGE_SIZE],
            "breadcrumbs_items": _breadcrumbs(
                {"url": reverse("api_client_index"), "label": "API 客户端"},
                {"url": "", "label": client.name},
            ),
        },
    )


@hooks.register("register_admin_urls")
def register_api_client_urls():
    return [
        path("settings/api-clients/", client_index, name="api_client_index"),
        path("settings/api-clients/new/", client_create, name="api_client_create"),
        path(
            "settings/api-clients/<int:pk>/",
            client_detail,
            name="api_client_detail",
        ),
    ]


class SuperuserMenuItem(MenuItem):
    def is_shown(self, request):
        return bool(getattr(request.user, "is_superuser", False))


@hooks.register("register_settings_menu_item")
def register_api_client_menu_item():
    return SuperuserMenuItem(
        "API 客户端",
        reverse("api_client_index"),
        icon_name="link",
        order=830,
    )
