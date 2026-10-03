"""Scrim administration (design 9.1, 14.2)."""

from functools import wraps

from django.contrib import messages
from django.core.exceptions import PermissionDenied
from django.http import Http404
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import path, reverse
from wagtail import hooks
from wagtail.admin.menu import MenuItem
from wagtail.admin.panels import FieldPanel, MultiFieldPanel
from wagtail.admin.ui.menus import MenuItem as ListingMenuItem
from wagtail.admin.views import generic
from wagtail.admin.viewsets.model import ModelViewSet
from wagtail.permission_policies import ModelPermissionPolicy
from wagtail.permissions import register_permission_policy

from core import admin_log
from scrims import services
from scrims.models import Scrim, ScrimStatus

ACTIONS = {
    "publish": ("发布内战", services.publish),
    "finish": ("标记为已结束", services.finish),
}
LOG_ACTIONS = {"publish": "scrims.publish", "finish": "scrims.finish"}


class ScrimIndexView(generic.IndexView):
    def get_delete_url(self, instance):
        # The listing asks only the model-level permission (round 115).
        if not services.can_delete(instance):
            return None
        return super().get_delete_url(instance)

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
            # Design 10.4 (v6.19): once per scrim, after a preview.
            buttons.append(
                ListingMenuItem(
                    "通知全体成员",
                    url=reverse("announce", args=["scrim", instance.pk]),
                    icon_name="mail",
                    priority=62,
                )
            )
            buttons.append(
                ListingMenuItem(
                    "标记为已结束",
                    url=reverse("scrim_action", args=[instance.pk, "finish"]),
                    icon_name="tick",
                    priority=61,
                )
            )
        if instance.status != ScrimStatus.DRAFT:
            buttons.append(
                ListingMenuItem(
                    "分队",
                    url=reverse("scrim_split", args=[instance.pk]),
                    icon_name="group",
                    priority=50,
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
        # Design 9.1 (v6.34): the start before this save, for 「时间改了」.
        form = getattr(self, "form", None)
        old_starts_at = form.initial.get("starts_at") if form is not None else None
        instance = super().save_instance()
        services.time_changed(instance, old_starts_at)
        if instance.created_by_id is None:
            instance.created_by = self.request.user
            instance.save(update_fields=["created_by"])
        services.after_change(instance, actor=self.request.user)
        return instance


class ScrimCreateView(ScrimSaveMixin, generic.CreateView):
    pass


class ScrimEditView(ScrimSaveMixin, generic.EditView):
    pass


class ScrimPermissionPolicy(ModelPermissionPolicy):
    """Round 115: only a draft nobody signed up for can be deleted; after that
    a scrim is cancelled, so signups and their emails stay accounted for."""

    def user_has_permission_for_instance(self, user, action, instance):
        if action == "delete" and not services.can_delete(instance):
            return False
        return super().user_has_permission_for_instance(user, action, instance)


register_permission_policy(Scrim, ScrimPermissionPolicy(Scrim))


class ScrimDeleteView(generic.DeleteView):
    """The delete button is hidden for the rest; a typed address is refused too."""

    def dispatch(self, request, *args, **kwargs):
        if not services.can_delete(self.object):
            messages.error(request, "发布过或有人报名的内战不能删除，只能取消。")
            return redirect("scrims:edit", self.object.pk)
        return super().dispatch(request, *args, **kwargs)


class ScrimViewSet(ModelViewSet):
    model = Scrim
    name = "scrims"
    icon = "group"
    menu_label = "内战活动"
    add_to_admin_menu = False
    copy_view_enabled = False
    inspect_view_enabled = True
    index_view_class = ScrimIndexView
    add_view_class = ScrimCreateView
    edit_view_class = ScrimEditView
    delete_view_class = ScrimDeleteView
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
        "内战活动",
        reverse("scrims:index"),
        icon_name="group",
        order=30,
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
    if action not in ACTIONS:
        raise Http404("没有这个操作。")
    scrim = get_object_or_404(Scrim, pk=pk)
    label, handler = ACTIONS[action]
    if request.method == "POST":
        try:
            handler(scrim=scrim, actor=request.user)
        except services.ScrimError as exc:
            messages.error(request, str(exc))
        else:
            admin_log.record(scrim, LOG_ACTIONS[action], request.user)
            messages.success(request, f"「{scrim.title}」已{label[:2]}。")
            if action == "publish" and request.POST.get("announce"):
                _announce_after_publish(request, scrim)
        return redirect("scrims:index")
    return render(
        request,
        "scrims/admin/confirm.html",
        {
            "page_title": label,
            "header_icon": "group",
            "scrim": scrim,
            "action_label": label,
            "announce": _announce_offer(scrim) if action == "publish" else None,
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
            admin_log.record(scrim, "scrims.cancel", request.user)
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
    from scrims import split_admin

    return [
        path("scrims/<int:pk>/cancel/", scrim_cancel, name="scrim_cancel"),
        path("scrims/<int:pk>/split/", split_admin.split_view, name="scrim_split"),
        path(
            "scrims/<int:pk>/split/text/",
            split_admin.copy_view,
            name="scrim_split_text",
        ),
        path("scrims/<int:pk>/<str:action>/", scrim_action, name="scrim_action"),
    ]


def _announce_offer(scrim) -> dict:
    """The 「同时通知全体成员」 box on the publish page (design 10.4)."""
    from core import services as core_services

    return {
        "count": core_services.recipient_count(scrim),
        "problem": core_services.announcement_problem("scrim", scrim, publishing=True),
    }


def _announce_after_publish(request, scrim) -> None:
    from core import services as core_services

    try:
        broadcast = core_services.announce(kind="scrim", obj=scrim, actor=request.user)
    except core_services.AnnouncementError as exc:
        messages.warning(request, f"没有通知全体成员：{exc}")
    else:
        messages.success(
            request, f"已开始通知全体成员（{broadcast.recipient_count} 人）。"
        )
