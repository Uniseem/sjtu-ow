"""Scrim administration (design 9.1, 14.2)."""

from functools import wraps

from django.contrib import messages
from django.core.exceptions import PermissionDenied
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import path, reverse
from wagtail import hooks
from wagtail.admin.menu import MenuItem
from wagtail.admin.panels import FieldPanel, MultiFieldPanel
from wagtail.admin.ui.menus import MenuItem as ListingMenuItem
from wagtail.admin.views import generic
from wagtail.admin.viewsets.model import ModelViewSet

from scrims import services
from scrims.models import Scrim, ScrimStatus

ACTIONS = {
    "publish": ("发布内战", services.publish),
    "finish": ("标记为已结束", services.finish),
}


class ScrimIndexView(generic.IndexView):
    def get_list_more_buttons(self, instance):
        buttons = super().get_list_more_buttons(instance)
        if instance.status == ScrimStatus.DRAFT:
            buttons.append(
                ListingMenuItem(
                    "发布",
                    url=reverse("scrim_action", args=[instance.pk, "publish"]),
                    icon_name="tick",
                    priority=60,
                )
            )
        if instance.status == ScrimStatus.PUBLISHED:
            buttons.append(
                ListingMenuItem(
                    "标记为已结束",
                    url=reverse("scrim_action", args=[instance.pk, "finish"]),
                    icon_name="tick",
                    priority=61,
                )
            )
        if instance.status != ScrimStatus.CANCELLED:
            buttons.append(
                ListingMenuItem(
                    "取消内战",
                    url=reverse("scrim_cancel", args=[instance.pk]),
                    icon_name="cross",
                    priority=70,
                )
            )
        return buttons


class ScrimSaveMixin:
    def save_instance(self):
        instance = super().save_instance()
        if instance.created_by_id is None:
            instance.created_by = self.request.user
            instance.save(update_fields=["created_by"])
        services.after_change(instance, actor=self.request.user)
        return instance


class ScrimCreateView(ScrimSaveMixin, generic.CreateView):
    pass


class ScrimEditView(ScrimSaveMixin, generic.EditView):
    pass


class ScrimViewSet(ModelViewSet):
    model = Scrim
    name = "scrims"
    icon = "group"
    menu_label = "内战"
    add_to_admin_menu = False
    copy_view_enabled = False
    inspect_view_enabled = True
    index_view_class = ScrimIndexView
    add_view_class = ScrimCreateView
    edit_view_class = ScrimEditView
    list_display = ["title", "status", "format", "starts_at", "signup_closes_at"]
    list_filter = ["status", "format", "sjtu_only"]
    search_fields = ["title", "description"]
    panels = [
        MultiFieldPanel(
            [FieldPanel("title"), FieldPanel("description")],
            heading="内容",
        ),
        MultiFieldPanel(
            [FieldPanel("starts_at"), FieldPanel("signup_closes_at")],
            heading="时间",
        ),
        MultiFieldPanel(
            [FieldPanel("format"), FieldPanel("sjtu_only")],
            heading="规则",
        ),
    ]


@hooks.register("register_admin_viewset")
def register_scrim_viewset():
    return ScrimViewSet()


class ScrimMenuItem(MenuItem):
    def is_shown(self, request):
        return services.can_manage(request.user)


@hooks.register("register_community_menu_item")
def register_scrim_menu_item():
    return ScrimMenuItem(
        "内战",
        reverse("scrims:index"),
        icon_name="group",
        order=160,
    )


def manager_required(view):
    @wraps(view)
    def wrapper(request, *args, **kwargs):
        if not services.can_manage(request.user):
            raise PermissionDenied("需要内战管理权限。")
        return view(request, *args, **kwargs)

    return wrapper


def _breadcrumbs(scrim):
    return [
        {"url": reverse("wagtailadmin_home"), "label": "首页"},
        {"url": reverse("scrims:index"), "label": "内战"},
        {"url": "", "label": scrim.title},
    ]


@manager_required
def scrim_action(request, pk, action):
    scrim = get_object_or_404(Scrim, pk=pk)
    label, handler = ACTIONS[action]
    if request.method == "POST":
        try:
            handler(scrim=scrim, actor=request.user)
        except services.ScrimError as exc:
            messages.error(request, str(exc))
        else:
            messages.success(request, f"「{scrim.title}」已{label[:2]}。")
        return redirect("scrims:index")
    return render(
        request,
        "scrims/admin/confirm.html",
        {
            "page_title": label,
            "header_icon": "group",
            "scrim": scrim,
            "action_label": label,
            "breadcrumbs_items": _breadcrumbs(scrim),
        },
    )


@manager_required
def scrim_cancel(request, pk):
    scrim = get_object_or_404(Scrim, pk=pk)
    if request.method == "POST":
        try:
            services.cancel_scrim(scrim=scrim, actor=request.user)
        except services.ScrimError as exc:
            messages.error(request, str(exc))
        else:
            messages.success(
                request, f"「{scrim.title}」已取消，已报名的人会收到邮件。"
            )
        return redirect("scrims:index")
    return render(
        request,
        "scrims/admin/confirm.html",
        {
            "page_title": "取消内战",
            "header_icon": "cross",
            "scrim": scrim,
            "action_label": "取消内战",
            "breadcrumbs_items": _breadcrumbs(scrim),
        },
    )


@hooks.register("register_admin_urls")
def register_scrim_urls():
    return [
        path("scrims/<int:pk>/cancel/", scrim_cancel, name="scrim_cancel"),
        path("scrims/<int:pk>/<str:action>/", scrim_action, name="scrim_action"),
    ]
