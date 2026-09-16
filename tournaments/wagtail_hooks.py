"""Tournament administration (design 8.1, 14.2)."""

from django.contrib import messages
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import path, reverse
from wagtail import hooks
from wagtail.admin.menu import MenuItem
from wagtail.admin.panels import FieldPanel, MultiFieldPanel
from wagtail.admin.ui.menus import MenuItem as ListingMenuItem
from wagtail.admin.views import generic
from wagtail.admin.viewsets.model import ModelViewSet

from tournaments import services
from tournaments.models import Tournament, TournamentStatus

ACTIONS = {
    "publish": ("发布赛事", services.publish),
    "finish": ("标记为已结束", services.finish),
}


class TournamentIndexView(generic.IndexView):
    def get_list_more_buttons(self, instance):
        buttons = super().get_list_more_buttons(instance)
        if instance.status == TournamentStatus.DRAFT:
            buttons.append(
                ListingMenuItem(
                    "发布",
                    url=reverse("tournament_action", args=[instance.pk, "publish"]),
                    icon_name="tick",
                    priority=60,
                )
            )
        if instance.status == TournamentStatus.PUBLISHED:
            buttons.append(
                ListingMenuItem(
                    "标记为已结束",
                    url=reverse("tournament_action", args=[instance.pk, "finish"]),
                    icon_name="tick",
                    priority=61,
                )
            )
        if instance.status != TournamentStatus.CANCELLED:
            buttons.append(
                ListingMenuItem(
                    "取消赛事",
                    url=reverse("tournament_cancel", args=[instance.pk]),
                    icon_name="cross",
                    priority=70,
                )
            )
        return buttons


class TournamentSaveMixin:
    def save_instance(self):
        instance = super().save_instance()
        if instance.created_by_id is None:
            instance.created_by = self.request.user
            instance.save(update_fields=["created_by"])
        warning = services.roster_min_warning(instance)
        if warning:
            messages.warning(self.request, warning)
        services.after_change(instance, actor=self.request.user)
        return instance


class TournamentCreateView(TournamentSaveMixin, generic.CreateView):
    pass


class TournamentEditView(TournamentSaveMixin, generic.EditView):
    pass


class TournamentViewSet(ModelViewSet):
    model = Tournament
    name = "tournaments"
    icon = "date"
    menu_label = "赛事"
    add_to_admin_menu = False
    copy_view_enabled = False
    inspect_view_enabled = True
    index_view_class = TournamentIndexView
    add_view_class = TournamentCreateView
    edit_view_class = TournamentEditView
    list_display = [
        "title",
        "status",
        "registration_opens_at",
        "registration_closes_at",
    ]
    list_filter = ["status", "review_mode", "sjtu_only"]
    search_fields = ["title", "summary"]
    panels = [
        MultiFieldPanel(
            [
                FieldPanel("title"),
                FieldPanel("summary"),
                FieldPanel("description"),
                FieldPanel("cover"),
            ],
            heading="内容",
        ),
        MultiFieldPanel(
            [
                FieldPanel("starts_at"),
                FieldPanel("registration_opens_at"),
                FieldPanel("registration_closes_at"),
            ],
            heading="时间",
        ),
        MultiFieldPanel(
            [
                FieldPanel("roster_min"),
                FieldPanel("roster_max"),
                FieldPanel("sjtu_only"),
                FieldPanel("review_mode"),
            ],
            heading="报名规则",
        ),
    ]


@hooks.register("register_admin_viewset")
def register_tournament_viewset():
    return TournamentViewSet()


class TournamentMenuItem(MenuItem):
    def is_shown(self, request):
        return services.can_manage(request.user)


@hooks.register("register_community_menu_item")
def register_tournament_menu_item():
    return TournamentMenuItem(
        "赛事",
        reverse("tournaments:index"),
        icon_name="date",
        order=150,
    )


def manager_required(view):
    from functools import wraps

    from django.core.exceptions import PermissionDenied

    @wraps(view)
    def wrapper(request, *args, **kwargs):
        if not services.can_manage(request.user):
            raise PermissionDenied("需要赛事管理权限。")
        return view(request, *args, **kwargs)

    return wrapper


@manager_required
def tournament_action(request, pk, action):
    tournament = get_object_or_404(Tournament, pk=pk)
    label, handler = ACTIONS[action]
    if request.method == "POST":
        try:
            handler(tournament=tournament, actor=request.user)
        except services.TournamentError as exc:
            messages.error(request, str(exc))
        else:
            messages.success(request, f"「{tournament.title}」已{label[:2]}。")
        return redirect("tournaments:index")
    return render(
        request,
        "tournaments/admin/confirm.html",
        {
            "page_title": label,
            "header_icon": "date",
            "tournament": tournament,
            "action_label": label,
            "needs_reason": False,
            "breadcrumbs_items": _breadcrumbs(tournament),
        },
    )


@manager_required
def tournament_cancel(request, pk):
    tournament = get_object_or_404(Tournament, pk=pk)
    if request.method == "POST":
        try:
            services.cancel(
                tournament=tournament,
                actor=request.user,
                reason=request.POST.get("reason", "")[:300],
            )
        except services.TournamentError as exc:
            messages.error(request, str(exc))
        else:
            messages.success(
                request,
                f"「{tournament.title}」已取消，已报名的队长会收到邮件。",
            )
        return redirect("tournaments:index")
    return render(
        request,
        "tournaments/admin/confirm.html",
        {
            "page_title": "取消赛事",
            "header_icon": "cross",
            "tournament": tournament,
            "action_label": "取消赛事",
            "needs_reason": True,
            "breadcrumbs_items": _breadcrumbs(tournament),
        },
    )


def _breadcrumbs(tournament):
    return [
        {"url": reverse("wagtailadmin_home"), "label": "首页"},
        {"url": reverse("tournaments:index"), "label": "赛事"},
        {"url": "", "label": tournament.title},
    ]


@hooks.register("register_admin_urls")
def register_tournament_admin_urls():
    return [
        path(
            "tournaments/<int:pk>/action/<str:action>/",
            tournament_action,
            name="tournament_action",
        ),
        path(
            "tournaments/<int:pk>/cancel/",
            tournament_cancel,
            name="tournament_cancel",
        ),
    ]
