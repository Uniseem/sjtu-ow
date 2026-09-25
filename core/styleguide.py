"""The design-system specimen page, /_styleguide/ (design 13.2.7).

Every component in every state on one page, with made-up sample data — no
database reads. Only people who can enter the admin see it; everyone else
gets a 404 so the page does not advertise itself.
"""

from __future__ import annotations

from datetime import datetime, timedelta

from django.http import Http404
from django.shortcuts import render
from django.utils import timezone
from django.views.decorators.http import require_GET

ADMIN_PERMISSION = "wagtailadmin.access_admin"

COLOURS = [
    ("交大红", "red", "bg-red", "#B2141A"),
    ("深红", "red-deep", "bg-red-deep", "#861116"),
    ("亮红", "red-bright", "bg-red-bright", "#EA4E4B"),
    ("红底", "red-tint", "bg-red-tint", "#FBEAE9"),
    ("页面", "canvas", "bg-canvas", "#F6F5F4"),
    ("面", "surface", "bg-surface", "#FFFFFF"),
    ("凹面", "sunken", "bg-sunken", "#EFEDEC"),
    ("发丝线", "line", "bg-line", "#DDD9D7"),
    ("粗线", "line-strong", "bg-line-strong", "#B6B0AE"),
    ("控件边框", "control", "bg-control", "#847C7A"),
    ("墨", "ink", "bg-ink", "#1D1716"),
    ("墨 2", "ink-2", "bg-ink-2", "#5C5452"),
    ("墨 3", "ink-3", "bg-ink-3", "#726A68"),
    ("夜", "night", "bg-night", "#141010"),
    ("夜 2", "night-2", "bg-night-2", "#1F1A19"),
    ("夜线", "night-line", "bg-night-line", "#3A3231"),
    ("夜字", "night-ink", "bg-night-ink", "#F5F2F1"),
    ("夜字 2", "night-ink-2", "bg-night-ink-2", "#ADA5A3"),
    ("夜字 3", "night-ink-3", "bg-night-ink-3", "#8F8785"),
    ("夜粗线", "night-line-strong", "bg-night-line-strong", "#5A5150"),
    ("夜控件边框", "night-control", "bg-night-control", "#736A69"),
    ("通过", "ok", "bg-ok", "#2F6F45"),
    ("提醒", "warn", "bg-warn", "#8F5B06"),
    ("信息", "info", "bg-info", "#3F6789"),
    ("夜通过", "ok-bright", "bg-ok-bright", "#7CC093"),
    ("夜提醒", "warn-bright", "bg-warn-bright", "#E0A84A"),
    ("夜信息", "info-bright", "bg-info-bright", "#8FB1CF"),
]

STATUSES = [
    ("live", "报名中"),
    ("ok", "已通过"),
    ("warn", "待审核"),
    ("info", "即将开始"),
    ("done", "已结束"),
    ("off", "已取消"),
    ("rejected", "已驳回"),
]

ICONS = [
    "search", "menu", "close", "arrow-right", "arrow-left", "arrow-up-right",
    "chevron-down", "chevron-right", "user", "users", "calendar", "clock",
    "trophy", "shield", "pen", "news", "info", "alert", "check",
    "check-circle", "x-circle", "plus", "lock", "mail", "id", "phone", "heart",
    "reply", "pin", "edit", "trash", "eye", "eye-off", "logout", "download",
    "external", "copy", "settings", "flag", "map", "role-tank", "role-damage",
    "role-support",
]  # fmt: skip


def sample_context():
    now = timezone.localtime()
    base = now.replace(hour=19, minute=30, second=0, microsecond=0)
    return {
        "colours": COLOURS,
        "statuses": STATUSES,
        "icons": ICONS,
        "sample_day": base + timedelta(days=3),
        "sample_close": base + timedelta(days=12),
        "sample_past": base - timedelta(days=40),
        "sample_year": datetime(base.year, 1, 1, tzinfo=base.tzinfo),
        "days": [
            {
                "date": (now + timedelta(days=offset)).date(),
                "count": {2: 1, 5: 2, 9: 1}.get(offset, 0),
                "today": offset == 0,
            }
            for offset in range(14)
        ],
        "rows": [
            (
                "暑期内战回顾：48 人、8 支队伍、一个晚上",
                "战报",
                "自动分队第一次在大规模内战里使用，分差最大的一场只有 3 分。",
            ),
            (
                "新赛季辅助位环境：从理解节奏开始",
                "攻略",
                "不讲数值，讲什么时候该交技能、什么时候该站出来。",
            ),
        ],
        "people": [
            ("夜航", "社长", "思源"),
            ("白露", "内战负责人", "东川路电竞"),
            ("Kairo", "", ""),
        ],
    }


@require_GET
def styleguide(request):
    user = request.user
    if not (user.is_authenticated and user.has_perm(ADMIN_PERMISSION)):
        raise Http404
    return render(request, "core/styleguide.html", sample_context())
