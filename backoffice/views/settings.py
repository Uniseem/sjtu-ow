"""全站设置 and 操作记录 (docs/admin.md 4.6), for superusers."""

from __future__ import annotations

from datetime import datetime, time

from django.contrib import messages
from django.shortcuts import redirect, render
from django.utils import timezone
from wagtail.log_actions import log
from wagtail.log_actions import registry as log_registry
from wagtail.models import ModelLogEntry, PageLogEntry

from accounts.models import User
from backoffice.forms import LogFilterForm, SiteSettingsForm
from backoffice.nav import placed
from backoffice.views.common import paginate
from core.models import SiteSettings

LOG_PER_PAGE = 50


@placed("settings", "site")
def site_settings(request):
    site = SiteSettings.load(request)
    form = SiteSettingsForm(request.POST or None, instance=site, user=request.user)
    if request.method == "POST" and form.is_valid():
        site = form.save()
        log(site, "wagtail.edit", user=request.user)
        messages.success(request, "全站设置已保存。")
        return redirect("backoffice:site_settings")
    return render(
        request,
        "backoffice/settings/site.html",
        {"page_title": "全站设置", "form": form},
    )


def _day_start(day):
    return timezone.make_aware(datetime.combine(day, time.min))


@placed("settings", "log")
def action_log(request):
    """Every entry, the pages' and the models', newest first."""
    form = LogFilterForm(request.GET or None)
    entries = []
    filters = {}
    if form.is_valid():
        if form.cleaned_data.get("action"):
            filters["action"] = form.cleaned_data["action"]
        if form.cleaned_data.get("since"):
            filters["timestamp__gte"] = _day_start(form.cleaned_data["since"])
        if form.cleaned_data.get("until"):
            filters["timestamp__lt"] = _day_start(form.cleaned_data["until"]) + (
                timezone.timedelta(days=1)
            )
    fields = ("pk", "timestamp", "action", "label", "user_id", "content_type_id")
    # Each side without its default ordering: SQLite takes ORDER BY only on
    # the union as a whole.
    pages = PageLogEntry.objects.filter(**filters).order_by().values(*fields)
    models = ModelLogEntry.objects.filter(**filters).order_by().values(*fields)
    union = pages.union(models, all=True).order_by("-timestamp", "-pk")
    page_obj, extra_query = paginate(request, union, LOG_PER_PAGE)
    users = User.objects.in_bulk({row["user_id"] for row in page_obj if row["user_id"]})
    for row in page_obj:
        person = users.get(row["user_id"])
        entries.append(
            {
                "timestamp": row["timestamp"],
                "action": log_registry.get_action_label(row["action"])
                if log_registry.action_exists(row["action"])
                else row["action"],
                "label": row["label"],
                "user": person.nickname if person else "系统",
            }
        )
    return render(
        request,
        "backoffice/settings/log.html",
        {
            "page_title": "操作记录",
            "form": form,
            "entries": entries,
            "page_obj": page_obj,
            "extra_query": extra_query,
        },
    )
