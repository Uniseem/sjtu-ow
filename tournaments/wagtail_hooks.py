"""Tournament administration (design 8.1, 14.2)."""

from django.contrib import messages
from django.db.models import Count, Q
from django.http import Http404
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import path, reverse
from wagtail import hooks
from wagtail.admin.forms import WagtailAdminModelForm
from wagtail.admin.menu import MenuItem
from wagtail.admin.panels import FieldPanel, MultiFieldPanel
from wagtail.admin.ui.menus import MenuItem as ListingMenuItem
from wagtail.admin.ui.tables import Column
from wagtail.admin.views import generic
from wagtail.admin.views.generic.models import CopyViewMixin
from wagtail.admin.viewsets.model import ModelViewSet
from wagtail.permission_policies import ModelPermissionPolicy
from wagtail.permissions import register_permission_policy

from content.widgets import MarkdownEditor
from core import admin_log
from tournaments import services
from tournaments.models import RegistrationStatus, Tournament, TournamentStatus

ACTIONS = {
    "publish": ("发布赛事", services.publish),
    "finish": ("标记为已结束", services.finish),
}
LOG_ACTIONS = {"publish": "tournaments.publish", "finish": "tournaments.finish"}


class TournamentAdminForm(WagtailAdminModelForm):
    """Design 8.1: 「报名自动通过」 and 「报名方式」 lock once anyone has signed up.

    Round 067: the old 「审核模式」 lock lived only in the API; the admin form
    never checked it. This form is the only place either can change.
    """

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if "roster_min" in self.fields:
            cap = services.team_max_members()
            self.fields["roster_min"].help_text = (
                f"整队报名时不能超过全站战队人数上限（现在是 {cap} 人，"
                "在全站设置里改），否则没有战队能报名。个人报名不受这条限制。"
            )

    def clean(self):
        cleaned = super().clean()
        # Round 119: say it on the field before saving, not in a toast after.
        # Only when these change: lowering the site cap later must not block
        # unrelated edits (the toast after saving still says it then).
        touched = {"roster_min", "registration_mode"} & set(self.changed_data)
        if (
            (touched or not self.instance.pk)
            and cleaned.get("roster_min")
            and cleaned.get("registration_mode")
        ):
            probe = Tournament(
                roster_min=cleaned["roster_min"],
                registration_mode=cleaned["registration_mode"],
            )
            warning = services.roster_min_warning(probe)
            if warning:
                self.add_error("roster_min", warning)
        if not self.instance.pk:
            return cleaned
        if "auto_approve" in self.changed_data and services.has_registrations(
            self.instance
        ):
            self.add_error("auto_approve", "已经有报名了，不能再改「报名自动通过」。")
        if "registration_mode" in self.changed_data and services.has_entries(
            self.instance
        ):
            self.add_error(
                "registration_mode", "已经有人报名了，不能再改「报名方式」。"
            )
        return cleaned


Tournament.base_form_class = TournamentAdminForm


def pending_review_url(tournament) -> str:
    """This tournament's registrations waiting for review (14.1, v6.71)."""
    return (
        reverse("registration_review_index")
        + f"?tournament={tournament.pk}&status={RegistrationStatus.PENDING}"
    )


class PendingColumn(Column):
    """「待审核」: how many wait, straight to them (design 14.1, v6.71)."""

    cell_template_name = "tournaments/admin/pending_cell.html"

    def get_cell_context_data(self, instance, parent_context):
        context = super().get_cell_context_data(instance, parent_context)
        context["count"] = getattr(instance, "pending_registrations", 0)
        context["url"] = pending_review_url(instance)
        return context


class TournamentIndexView(generic.IndexView):
    def get_base_queryset(self):
        return (
            super()
            .get_base_queryset()
            .annotate(
                pending_registrations=Count(
                    "registrations",
                    filter=Q(registrations__status=RegistrationStatus.PENDING),
                )
            )
        )

    def get_delete_url(self, instance):
        # The listing asks only the model-level permission (round 115).
        if not services.can_delete(instance):
            return None
        return super().get_delete_url(instance)

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
            # Design 10.4 (v6.19): once per tournament, after a preview.
            buttons.append(
                ListingMenuItem(
                    "通知全体成员",
                    url=reverse("announce", args=["tournament", instance.pk]),
                    icon_name="mail",
                    priority=62,
                )
            )
            buttons.append(
                ListingMenuItem(
                    "标记为已结束",
                    url=reverse("tournament_action", args=[instance.pk, "finish"]),
                    icon_name="tick",
                    priority=61,
                )
            )
        buttons.append(
            ListingMenuItem(
                "审核报名",
                url=pending_review_url(instance),
                icon_name="tasks",
                priority=63,
            )
        )
        if instance.takes_individuals:
            buttons.append(
                ListingMenuItem(
                    "队伍编排",
                    url=reverse("tournament_teams_board", args=[instance.pk]),
                    icon_name="group",
                    priority=65,
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
        # Design 8.1 (v6.34): the start before this save, for 「时间改了」.
        form = getattr(self, "form", None)
        old_starts_at = form.initial.get("starts_at") if form is not None else None
        instance = super().save_instance()
        services.time_changed(instance, old_starts_at)
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


class TournamentCopyView(CopyViewMixin, TournamentCreateView):
    """「复制」 (design 14.2, v6.51): the new-tournament form filled from this one."""

    def get_initial_form_instance(self):
        return services.copy_for_new(super().get_initial_form_instance())


class TournamentPermissionPolicy(ModelPermissionPolicy):
    """Design 8.1 (round 115): only a draft never published can be deleted;
    after that a tournament is cancelled, so registrations and their logs stay."""

    def user_has_permission_for_instance(self, user, action, instance):
        if action == "delete" and not services.can_delete(instance):
            return False
        return super().user_has_permission_for_instance(user, action, instance)


register_permission_policy(Tournament, TournamentPermissionPolicy(Tournament))


class TournamentDeleteView(generic.DeleteView):
    """The delete button is hidden for the rest; a typed address is refused too."""

    def dispatch(self, request, *args, **kwargs):
        if not services.can_delete(self.object):
            messages.error(request, "发布过的赛事不能删除，只能取消。")
            return redirect("tournaments:edit", self.object.pk)
        return super().dispatch(request, *args, **kwargs)


class TournamentViewSet(ModelViewSet):
    model = Tournament
    name = "tournaments"
    icon = "date"
    menu_label = "赛事"
    add_to_admin_menu = False
    inspect_view_enabled = True
    index_view_class = TournamentIndexView
    add_view_class = TournamentCreateView
    copy_view_class = TournamentCopyView
    edit_view_class = TournamentEditView
    delete_view_class = TournamentDeleteView
    list_display = [
        "title",
        "status",
        "registration_opens_at",
        "registration_closes_at",
        PendingColumn("pending_registrations", label="待审核"),
    ]
    list_filter = ["status", "registration_mode", "auto_approve", "sjtu_only"]
    search_fields = ["title", "summary"]
    panels = [
        MultiFieldPanel(
            [
                FieldPanel("title"),
                FieldPanel("summary"),
                FieldPanel("description", widget=MarkdownEditor),
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
                FieldPanel("registration_mode"),
                FieldPanel("roster_min"),
                FieldPanel("roster_max"),
                FieldPanel("sjtu_only"),
                FieldPanel("auto_approve"),
            ],
            heading="报名规则",
        ),
        FieldPanel("participant_contact"),
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
        order=10,
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
    if action not in ACTIONS:
        raise Http404("没有这个操作。")
    tournament = get_object_or_404(Tournament, pk=pk)
    label, handler = ACTIONS[action]
    if request.method == "POST":
        try:
            handler(tournament=tournament, actor=request.user)
        except services.TournamentError as exc:
            messages.error(request, str(exc))
        else:
            admin_log.record(tournament, LOG_ACTIONS[action], request.user)
            messages.success(request, f"「{tournament.title}」已{label[:2]}。")
            if action == "publish" and request.POST.get("announce"):
                _announce_after_publish(request, tournament)
        return redirect("tournaments:index")
    return render(
        request,
        "tournaments/admin/confirm.html",
        {
            "page_title": label,
            "header_icon": "date",
            "tournament": tournament,
            "action_label": label,
            "announce": _announce_offer(tournament) if action == "publish" else None,
            "needs_reason": False,
            "breadcrumbs_items": _breadcrumbs(tournament),
        },
    )


@manager_required
def tournament_cancel(request, pk):
    tournament = get_object_or_404(Tournament, pk=pk)
    if request.method == "POST":
        try:
            reason = request.POST.get("reason", "")[:300]
            services.cancel(tournament=tournament, actor=request.user, reason=reason)
        except services.TournamentError as exc:
            messages.error(request, str(exc))
        else:
            admin_log.record(
                tournament, "tournaments.cancel", request.user, reason=reason
            )
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


@hooks.register("register_log_actions")
def register_export_log_action(actions):
    from tournaments.review_admin import EXPORT_LOG_ACTION

    actions.register_action(EXPORT_LOG_ACTION, "导出报名名单", "导出了报名名单")


@hooks.register("register_community_menu_item")
def register_review_menu_item():
    return TournamentMenuItem(
        "报名审核",
        reverse("registration_review_index"),
        icon_name="tasks",
        order=20,
    )


@hooks.register("register_admin_urls")
def register_tournament_admin_urls():
    from tournaments import review_admin, teams_admin

    return [
        path(
            "tournaments/<id:pk>/teams/",
            teams_admin.board_view,
            name="tournament_teams_board",
        ),
        path(
            "registrations/",
            review_admin.review_index,
            name="registration_review_index",
        ),
        path(
            "registrations/<id:pk>/",
            review_admin.review_detail,
            name="registration_review_detail",
        ),
        path(
            "registrations/<id:pk>/action/",
            review_admin.review_action,
            name="registration_review_action",
        ),
        path(
            "registrations/bulk-approve/",
            review_admin.review_bulk_approve,
            name="registration_review_bulk",
        ),
        path(
            "registrations/export.csv",
            review_admin.review_export,
            name="registration_review_export",
        ),
        path(
            "tournaments/<id:pk>/action/<str:action>/",
            tournament_action,
            name="tournament_action",
        ),
        path(
            "tournaments/<id:pk>/cancel/",
            tournament_cancel,
            name="tournament_cancel",
        ),
    ]


def _announce_offer(tournament) -> dict:
    """The 「同时通知全体成员」 box on the publish page (design 10.4)."""
    from core import services as core_services

    return {
        "count": core_services.recipient_count(tournament),
        "problem": core_services.announcement_problem(
            "tournament", tournament, publishing=True
        ),
    }


def _announce_after_publish(request, tournament) -> None:
    from core import services as core_services

    try:
        broadcast = core_services.announce(
            kind="tournament", obj=tournament, actor=request.user
        )
    except core_services.AnnouncementError as exc:
        messages.warning(request, f"没有通知全体成员：{exc}")
    else:
        messages.success(
            request, f"已开始通知全体成员（{broadcast.recipient_count} 人）。"
        )
