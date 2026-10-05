"""赛事 and 内战 (docs/admin.md 4.3): the lists, the forms, copy and delete.

The pages to publish, finish, cancel, form teams and split are the apps'
own (tournaments.admin_views, scrims.admin_views, the two boards). Saving
does what the Wagtail views did: 「时间改了」 with the start before this
save, the creator filled in, the roster warning, ``after_change``. Since
v7.10 (design 13.17) the forms save themselves; something new exists from
its first change, required fields empty or not, and publishing checks them.
"""

from __future__ import annotations

from dataclasses import dataclass

from django.contrib import messages
from django.db.models import Count, F, Q
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from wagtail.log_actions import log

from backoffice.forms import ScrimForm, TournamentForm
from backoffice.nav import placed
from backoffice.views.common import paginate, search_text
from core import autosave
from scrims import services as scrim_services
from scrims.models import Scrim, ScrimStatus
from tournaments import services as tournament_services
from tournaments.models import (
    RegistrationMode,
    RegistrationStatus,
    Tournament,
    TournamentStatus,
)

PER_PAGE = 30
UNNAMED = {"tournament": "（未命名赛事）", "scrim": "（未命名内战）"}


def _autosave(request, form, kind, fresh):
    """Save what may be saved now (design 13.17, v7.10). New: created from
    the first change with the fields that are fine (``fresh`` makes the
    unsaved one as it stood, a copy's fields included). Existing: those
    fields written over what is stored; 「时间改了」 noted; then the pages
    and the reminders follow (``after_change``, its tasks once each)."""
    user = request.user
    services = tournament_services if kind == "tournament" else scrim_services
    valid = form.is_valid()
    outcome = autosave.Outcome(errors={} if valid else autosave.errors_of(form))
    obj = form.instance
    if obj.pk is None:
        obj, outcome.saved = autosave.new_from_valid_fields(form, fresh())
        if obj.created_by_id is None:
            obj.created_by = user
        obj.save()
        log(obj, "wagtail.create", user=user, title=obj.title or UNNAMED[kind])
        edit = "tournaments:edit" if kind == "tournament" else "scrims:edit"
        action = "tournament_action" if kind == "tournament" else "scrim_action"
        outcome.location = reverse(edit, args=[obj.pk])
        outcome.replace["[data-event-next]"] = (
            '<span class="b-formbar__note" data-event-next>已经建成草稿。填好以后'
            f'<a class="c-link" href="{reverse(action, args=[obj.pk, "publish"])}">'
            "发布</a>。</span>"
        )
        services.after_change(obj, actor=user)
        return autosave.respond(outcome)
    old_starts_at = form.initial.get("starts_at")
    outcome.saved = autosave.save_valid_fields(form)
    if outcome.saved:
        obj = form.instance
        autosave.log_edit(obj, user)
        if "starts_at" in outcome.saved:
            services.note_time_change(obj, old_starts_at)
        services.after_change(obj, actor=user)
    return autosave.respond(outcome)


@dataclass(frozen=True)
class Item:
    label: str
    url: str
    danger: bool = False


def pending_review_url(tournament) -> str:
    return (
        reverse("registration_review_index")
        + f"?tournament={tournament.pk}&status={RegistrationStatus.PENDING}"
    )


def sent_counts(kind: str, objs) -> dict[tuple[int, str], int]:
    """How often each mail went out about these (design 10.4, v7.5), in one
    query for a whole page: (id, audience) -> count."""
    from core.models import Broadcast

    rows = (
        Broadcast.objects.filter(
            kind=kind,
            object_id__in=[obj.pk for obj in objs],
            waits_for_publish=False,
        )
        .values("object_id", "audience")
        .annotate(total=Count("pk"))
    )
    return {(row["object_id"], row["audience"]): row["total"] for row in rows}


def notice_items(kind: str, obj, sent: dict) -> list[Item]:
    """「通知全体成员」 and 「通知报名的人」: both may go out again (v7.5),
    so each says how often it has."""
    url = reverse("announce", args=[kind, obj.pk])
    items = []
    for label, audience, link in (
        ("通知全体成员", "everyone", url),
        ("通知报名的人", "participants", url + "?to=participants"),
    ):
        times = sent.get((obj.pk, audience), 0)
        items.append(Item(f"{label}（发过 {times} 次）" if times else label, link))
    return items


def tournament_items(tournament, sent: dict | None = None) -> list[Item]:
    """「更多」 by status (design 14.2): what can be done to this one now."""
    items = []
    if tournament.status == TournamentStatus.DRAFT:
        items.append(
            Item("发布", reverse("tournament_action", args=[tournament.pk, "publish"]))
        )
    if tournament.status == TournamentStatus.PUBLISHED:
        items.extend(notice_items("tournament", tournament, sent or {}))
        items.append(
            Item(
                "标记为已结束",
                reverse("tournament_action", args=[tournament.pk, "finish"]),
            )
        )
    items.append(Item("审核报名", pending_review_url(tournament)))
    if tournament.takes_individuals:
        items.append(
            Item("队伍编排", reverse("tournament_teams_board", args=[tournament.pk]))
        )
    items.append(Item("复制", reverse("tournaments:copy", args=[tournament.pk])))
    unfinished = tournament.status == TournamentStatus.DRAFT and bool(
        tournament_services.missing(tournament)
    )
    if tournament.status != TournamentStatus.CANCELLED and not unfinished:
        items.append(
            Item(
                "取消赛事",
                reverse("tournament_cancel", args=[tournament.pk]),
                danger=True,
            )
        )
    if tournament_services.can_delete(tournament):
        items.append(
            Item(
                "删除", reverse("tournaments:delete", args=[tournament.pk]), danger=True
            )
        )
    return items


def scrim_items(scrim, sent: dict | None = None) -> list[Item]:
    items = []
    if scrim.status == ScrimStatus.DRAFT:
        items.append(Item("发布", reverse("scrim_action", args=[scrim.pk, "publish"])))
    if scrim.status == ScrimStatus.PUBLISHED:
        items.extend(notice_items("scrim", scrim, sent or {}))
        items.append(
            Item("标记为已结束", reverse("scrim_action", args=[scrim.pk, "finish"]))
        )
    if scrim.status != ScrimStatus.DRAFT:
        items.append(Item("分队", reverse("scrim_split", args=[scrim.pk])))
    items.append(Item("复制", reverse("scrims:copy", args=[scrim.pk])))
    unfinished = scrim.status == ScrimStatus.DRAFT and bool(
        scrim_services.missing(scrim)
    )
    if scrim.status != ScrimStatus.CANCELLED and not unfinished:
        items.append(
            Item("取消内战", reverse("scrim_cancel", args=[scrim.pk]), danger=True)
        )
    if scrim_services.can_delete(scrim):
        items.append(
            Item("删除", reverse("scrims:delete", args=[scrim.pk]), danger=True)
        )
    return items


# --- tournaments --------------------------------------------------------------


@placed("events", "tournaments")
def tournament_list(request):
    tournaments = Tournament.objects.annotate(
        pending=Count(
            "registrations",
            filter=Q(registrations__status=RegistrationStatus.PENDING),
        )
    ).order_by(
        # A draft without times yet (v7.10) is one being written: on top.
        F("registration_opens_at").desc(nulls_first=True),
        "-pk",
    )
    query = search_text(request)
    if query:
        tournaments = tournaments.filter(
            Q(title__icontains=query) | Q(summary__icontains=query)
        )
    status = request.GET.get("status") or ""
    if status in TournamentStatus.values:
        tournaments = tournaments.filter(status=status)
    mode = request.GET.get("mode") or ""
    if mode in RegistrationMode.values:
        tournaments = tournaments.filter(registration_mode=mode)
    page_obj, extra_query = paginate(request, tournaments, PER_PAGE)
    sent = sent_counts("tournament", page_obj)
    return render(
        request,
        "backoffice/events/tournaments.html",
        {
            "page_title": "赛事",
            "rows": [
                (t, tournament_items(t, sent), pending_review_url(t)) for t in page_obj
            ],
            "page_obj": page_obj,
            "extra_query": extra_query,
            "query": query,
            "status": status,
            "statuses": TournamentStatus.choices,
            "mode": mode,
            "modes": RegistrationMode.choices,
        },
    )


def _save_tournament(request, form, *, created: bool):
    old_starts_at = form.initial.get("starts_at")
    tournament = form.save(commit=False)
    if tournament.created_by_id is None:
        tournament.created_by = request.user
    tournament.save()
    log(tournament, "wagtail.create" if created else "wagtail.edit", user=request.user)
    tournament_services.note_time_change(tournament, old_starts_at)
    warning = tournament_services.roster_min_warning(tournament)
    if warning:
        messages.warning(request, warning)
    tournament_services.after_change(tournament, actor=request.user)
    messages.success(request, f"赛事「{tournament.title}」已保存。")
    return tournament


def _tournament_form_page(request, form, *, title, tournament=None, copied_from=None):
    return render(
        request,
        "backoffice/events/event_form.html",
        {
            "page_title": title,
            "form": form,
            "item": tournament,
            "kind": "tournament",
            "public_url": tournament.get_absolute_url() if tournament else "",
            "items": tournament_items(
                tournament, sent_counts("tournament", [tournament])
            )
            if tournament
            else [],
            "copied_from": copied_from,
            "back_url": reverse("tournaments:index"),
            "back_label": "赛事",
        },
    )


@placed("events", "tournaments")
def tournament_add(request):
    form = TournamentForm(
        request.POST or None, instance=Tournament(), user=request.user
    )
    if autosave.wants(request):
        return _autosave(request, form, "tournament", Tournament)
    if request.method == "POST" and form.is_valid():
        tournament = _save_tournament(request, form, created=True)
        return redirect("tournaments:edit", tournament.pk)
    return _tournament_form_page(request, form, title="新建赛事")


@placed("events", "tournaments")
def tournament_edit(request, pk):
    tournament = get_object_or_404(Tournament, pk=pk)
    form = TournamentForm(request.POST or None, instance=tournament, user=request.user)
    if autosave.wants(request):
        return _autosave(request, form, "tournament", None)
    if request.method == "POST" and form.is_valid():
        _save_tournament(request, form, created=False)
        return redirect("tournaments:edit", tournament.pk)
    tournament.refresh_from_db()
    return _tournament_form_page(
        request,
        form,
        title=tournament.title or UNNAMED["tournament"],
        tournament=tournament,
    )


@placed("events", "tournaments")
def tournament_copy(request, pk):
    """「复制」 (design 14.2, v6.51): the listed fields, times whole weeks on."""
    source = get_object_or_404(Tournament, pk=pk)
    form = TournamentForm(
        request.POST or None,
        instance=tournament_services.copy_for_new(source),
        user=request.user,
    )
    if autosave.wants(request):
        return _autosave(
            request,
            form,
            "tournament",
            lambda: tournament_services.copy_for_new(source),
        )
    if request.method == "POST" and form.is_valid():
        tournament = _save_tournament(request, form, created=True)
        return redirect("tournaments:edit", tournament.pk)
    return _tournament_form_page(
        request, form, title=f"复制赛事：{source.title}", copied_from=source
    )


@placed("events", "tournaments")
def tournament_delete(request, pk):
    """Only a draft never published (round 115); the rest are cancelled."""
    tournament = get_object_or_404(Tournament, pk=pk)
    if not tournament_services.can_delete(tournament):
        messages.error(request, "发布过的赛事不能删除，只能取消。")
        return redirect("tournaments:edit", tournament.pk)
    if request.method == "POST":
        title = tournament.title
        log(tournament, "wagtail.delete", user=request.user)
        tournament.delete()
        messages.success(request, f"赛事「{title}」已删除。")
        return redirect("tournaments:index")
    return render(
        request,
        "backoffice/confirm_delete.html",
        {
            "page_title": f"删除赛事：{tournament.title}",
            "what": "这项赛事草稿",
            "back_url": reverse("tournaments:edit", args=[tournament.pk]),
            "back_label": tournament.title,
        },
    )


# --- scrims ---------------------------------------------------------------------------


@placed("events", "scrims")
def scrim_list(request):
    scrims = Scrim.objects.annotate(signup_total=Count("signups")).order_by(
        F("starts_at").desc(nulls_first=True), "-pk"
    )
    query = search_text(request)
    if query:
        scrims = scrims.filter(
            Q(title__icontains=query) | Q(description__icontains=query)
        )
    status = request.GET.get("status") or ""
    if status in ScrimStatus.values:
        scrims = scrims.filter(status=status)
    page_obj, extra_query = paginate(request, scrims, PER_PAGE)
    sent = sent_counts("scrim", page_obj)
    return render(
        request,
        "backoffice/events/scrims.html",
        {
            "page_title": "内战",
            "rows": [(scrim, scrim_items(scrim, sent)) for scrim in page_obj],
            "page_obj": page_obj,
            "extra_query": extra_query,
            "query": query,
            "status": status,
            "statuses": ScrimStatus.choices,
        },
    )


def _save_scrim(request, form, *, created: bool):
    old_starts_at = form.initial.get("starts_at")
    scrim = form.save(commit=False)
    if scrim.created_by_id is None:
        scrim.created_by = request.user
    scrim.save()
    log(scrim, "wagtail.create" if created else "wagtail.edit", user=request.user)
    scrim_services.note_time_change(scrim, old_starts_at)
    scrim_services.after_change(scrim, actor=request.user)
    messages.success(request, f"内战「{scrim.title}」已保存。")
    return scrim


def _scrim_form_page(request, form, *, title, scrim=None, copied_from=None):
    return render(
        request,
        "backoffice/events/event_form.html",
        {
            "page_title": title,
            "form": form,
            "item": scrim,
            "kind": "scrim",
            "public_url": reverse("scrim_detail", args=[scrim.pk]) if scrim else "",
            "items": scrim_items(scrim, sent_counts("scrim", [scrim])) if scrim else [],
            "copied_from": copied_from,
            "back_url": reverse("scrims:index"),
            "back_label": "内战",
        },
    )


@placed("events", "scrims")
def scrim_add(request):
    form = ScrimForm(request.POST or None, instance=Scrim())
    if autosave.wants(request):
        return _autosave(request, form, "scrim", Scrim)
    if request.method == "POST" and form.is_valid():
        scrim = _save_scrim(request, form, created=True)
        return redirect("scrims:edit", scrim.pk)
    return _scrim_form_page(request, form, title="新建内战")


@placed("events", "scrims")
def scrim_edit(request, pk):
    scrim = get_object_or_404(Scrim, pk=pk)
    form = ScrimForm(request.POST or None, instance=scrim)
    if autosave.wants(request):
        return _autosave(request, form, "scrim", None)
    if request.method == "POST" and form.is_valid():
        _save_scrim(request, form, created=False)
        return redirect("scrims:edit", scrim.pk)
    scrim.refresh_from_db()
    return _scrim_form_page(
        request, form, title=scrim.title or UNNAMED["scrim"], scrim=scrim
    )


@placed("events", "scrims")
def scrim_copy(request, pk):
    source = get_object_or_404(Scrim, pk=pk)
    form = ScrimForm(request.POST or None, instance=scrim_services.copy_for_new(source))
    if autosave.wants(request):
        return _autosave(
            request, form, "scrim", lambda: scrim_services.copy_for_new(source)
        )
    if request.method == "POST" and form.is_valid():
        scrim = _save_scrim(request, form, created=True)
        return redirect("scrims:edit", scrim.pk)
    return _scrim_form_page(
        request, form, title=f"复制内战：{source.title}", copied_from=source
    )


@placed("events", "scrims")
def scrim_delete(request, pk):
    """Only a draft nobody signed up for (round 115)."""
    scrim = get_object_or_404(Scrim, pk=pk)
    if not scrim_services.can_delete(scrim):
        messages.error(request, "发布过或有人报名的内战不能删除，只能取消。")
        return redirect("scrims:edit", scrim.pk)
    if request.method == "POST":
        title = scrim.title
        log(scrim, "wagtail.delete", user=request.user)
        scrim.delete()
        messages.success(request, f"内战「{title}」已删除。")
        return redirect("scrims:index")
    return render(
        request,
        "backoffice/confirm_delete.html",
        {
            "page_title": f"删除内战：{scrim.title}",
            "what": "这场内战草稿",
            "back_url": reverse("scrims:edit", args=[scrim.pk]),
            "back_label": scrim.title,
        },
    )


ANNOUNCE_PLACES = {
    "article": ("content", "articles"),
    "tournament": ("events", "tournaments"),
    "scrim": ("events", "scrims"),
}


def announce(request, kind, pk):
    """「通知全体成员」 (design 10.4), in the section of what is announced."""
    from core.announce_admin import announce_view

    section, tab = ANNOUNCE_PLACES.get(kind, ("home", "home"))
    return placed(section, tab)(announce_view)(request, kind=kind, pk=pk)
