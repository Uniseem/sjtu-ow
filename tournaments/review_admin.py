"""Registration review in the Wagtail admin (design 8.7)."""

from __future__ import annotations

import csv
import logging
from functools import wraps

from django.contrib import messages
from django.core.exceptions import PermissionDenied
from django.core.paginator import Paginator
from django.http import HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone
from django.views.decorators.http import require_POST
from wagtail.log_actions import log as wagtail_log

from tournaments import registration as registration_service
from tournaments import services
from tournaments.models import Registration, RegistrationStatus, Tournament

logger = logging.getLogger(__name__)

PAGE_SIZE = 25
EXPORT_LOG_ACTION = "tournaments.export_registrations"


def reviewer_required(view):
    @wraps(view)
    def wrapper(request, *args, **kwargs):
        if not services.can_manage(request.user):
            raise PermissionDenied("需要赛事管理权限。")
        return view(request, *args, **kwargs)

    return wrapper


def can_see_contacts(user) -> bool:
    return bool(
        getattr(user, "is_superuser", False)
        or user.has_perm("accounts.view_contactmethod")
    )


def local_actions(registration) -> dict:
    """Which buttons to show for this status (design 8.5, 8.7).

    Ad-hoc teams are managed on the board (design 8.8.2), never here.
    """
    if registration.team_id is None:
        return {"approve": False, "reject": False, "revoke": False}
    status = registration.status
    return {
        "approve": status == RegistrationStatus.PENDING,
        "reject": status == RegistrationStatus.PENDING,
        "revoke": status == RegistrationStatus.APPROVED,
    }


def _filtered(request):
    queryset = (
        Registration.objects.select_related("tournament", "team")
        .prefetch_related("members")
        .order_by("-submitted_at")
    )
    status = request.GET.get("status", RegistrationStatus.PENDING)
    tournament_id = request.GET.get("tournament", "")
    if status:
        queryset = queryset.filter(status=status)
    if tournament_id:
        queryset = queryset.filter(tournament_id=tournament_id)
    return queryset, status, tournament_id


@reviewer_required
def review_index(request):
    queryset, status, tournament_id = _filtered(request)
    page = Paginator(queryset, PAGE_SIZE).get_page(request.GET.get("page"))
    return render(
        request,
        "tournaments/admin/review_index.html",
        {
            "page_title": "报名审核",
            "header_icon": "tasks",
            "registrations": page,
            "status": status,
            "tournament_id": tournament_id,
            "statuses": RegistrationStatus.choices,
            "tournaments": Tournament.objects.order_by("-registration_opens_at"),
            "breadcrumbs_items": [
                {"url": reverse("wagtailadmin_home"), "label": "首页"},
                {"url": "", "label": "报名审核"},
            ],
        },
    )


@reviewer_required
def review_detail(request, pk):
    registration = get_object_or_404(
        Registration.objects.select_related("tournament", "team"), pk=pk
    )
    roster = list(registration.members.select_related("user"))
    roster_ids = {member.user_id for member in roster}
    current = {}
    if registration.team_id is not None:
        current = {
            membership.user_id: membership.user
            for membership in registration.team.memberships.select_related("user")
        }
    contacts = {}
    if can_see_contacts(request.user):
        from accounts.models import ContactMethod

        for contact in ContactMethod.objects.filter(user_id__in=roster_ids):
            contacts.setdefault(contact.user_id, []).append(
                f"{contact.get_type_display()} {contact.value}"
            )
    rows = [
        {"member": member, "contacts": contacts.get(member.user_id, [])}
        for member in roster
    ]
    return render(
        request,
        "tournaments/admin/review_detail.html",
        {
            "page_title": f"{registration.team_name} · {registration.tournament.title}",
            "header_icon": "tasks",
            "registration": registration,
            "is_adhoc": registration.team_id is None,
            "rows": rows,
            "show_contacts": can_see_contacts(request.user),
            "added": [
                user for user_id, user in current.items() if user_id not in roster_ids
            ],
            "removed": [member for member in roster if member.user_id not in current],
            "logs": registration.logs.select_related("actor_user"),
            "actions": local_actions(registration),
            "breadcrumbs_items": [
                {"url": reverse("wagtailadmin_home"), "label": "首页"},
                {"url": reverse("registration_review_index"), "label": "报名审核"},
                {"url": "", "label": registration.team_name},
            ],
        },
    )


@reviewer_required
@require_POST
def review_action(request, pk):
    registration = get_object_or_404(Registration, pk=pk)
    action = request.POST.get("action", "")
    note = request.POST.get("note", "")
    try:
        if action == "approve":
            registration_service.approve(registration=registration, actor=request.user)
        elif action in ("reject", "revoke"):
            registration_service.reject(
                registration=registration, actor=request.user, note=note
            )
        else:
            raise registration_service.RegistrationError("未知的操作")
    except registration_service.RegistrationError as exc:
        messages.error(request, str(exc))
    else:
        registration.refresh_from_db()
        messages.success(
            request,
            f"「{registration.team_name}」现在是{registration.get_status_display()}。",
        )
    return redirect("registration_review_detail", pk=pk)


@reviewer_required
@require_POST
def review_bulk_approve(request):
    ids = request.POST.getlist("registration")
    approved = 0
    for pk in ids:
        registration = Registration.objects.filter(pk=pk).first()
        if registration is None:
            continue
        try:
            registration_service.approve(registration=registration, actor=request.user)
        except registration_service.RegistrationError as exc:
            messages.error(request, f"「{registration.team_name}」：{exc}")
        else:
            approved += 1
    if approved:
        messages.success(request, f"已通过 {approved} 条报名。")
    return redirect(request.POST.get("next") or "registration_review_index")


@reviewer_required
def review_export(request):
    """CSV of the current filter (design 8.7). Exports are logged."""
    queryset, status, tournament_id = _filtered(request)
    show_contacts = can_see_contacts(request.user)
    response = HttpResponse(content_type="text/csv; charset=utf-8")
    stamp = timezone.localtime().strftime("%Y%m%d-%H%M")
    response["Content-Disposition"] = (
        f'attachment; filename="registrations-{stamp}.csv"'
    )
    response.write("﻿")  # BOM so Excel reads UTF-8
    writer = csv.writer(response)
    header = [
        "赛事",
        "战队",
        "状态",
        "名单版本",
        "提交时间",
        "昵称",
        "游戏 ID",
        "是否交大",
        "是否队长",
    ]
    if show_contacts:
        header.append("联系方式")
    writer.writerow(header)

    contacts = {}
    if show_contacts:
        from accounts.models import ContactMethod

        for contact in ContactMethod.objects.all():
            contacts.setdefault(contact.user_id, []).append(
                f"{contact.get_type_display()} {contact.value}"
            )

    for registration in queryset:
        for member in registration.members.all():
            row = [
                registration.tournament.title,
                registration.team_name,
                registration.get_status_display(),
                registration.roster_version,
                timezone.localtime(registration.submitted_at).strftime(
                    "%Y-%m-%d %H:%M"
                ),
                member.nickname,
                member.battletag,
                "是" if member.is_sjtu else "否",
                "是" if member.is_captain else "否",
            ]
            if show_contacts:
                row.append("；".join(contacts.get(member.user_id, [])))
            writer.writerow(row)

    _log_export(request, queryset, show_contacts, tournament_id, status)
    return response


def _log_export(request, queryset, show_contacts, tournament_id, status):
    """Design 8.7: an export with contact details must leave a trace.

    One log entry per tournament in the result, so the trace shows up on the
    tournament whose roster was exported.
    """
    tournament_ids = list(queryset.values_list("tournament_id", flat=True).distinct())
    if tournament_id and int(tournament_id) not in tournament_ids:
        tournament_ids.append(int(tournament_id))
    tournaments = list(Tournament.objects.filter(pk__in=tournament_ids))
    detail = (
        f"导出报名 CSV：状态={status or '全部'}，{queryset.count()} 条"
        f"{'（含联系方式）' if show_contacts else ''}"
    )
    logger.info("%s（操作人 %s）", detail, request.user)
    for tournament in tournaments:
        try:
            wagtail_log(
                instance=tournament,
                action=EXPORT_LOG_ACTION,
                user=request.user,
                data={"detail": detail, "with_contacts": show_contacts},
            )
        except Exception:  # noqa: BLE001 — logging must not break the download
            logger.warning("导出留痕失败", exc_info=True)
