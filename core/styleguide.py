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
    ("页面", "bg", "bg-bg", "#F5F6F8"),
    ("卡片、页头", "surface", "bg-surface", "#FFFFFF"),
    ("表头、占位、日期块", "surface-2", "bg-surface-2", "#EEF0F3"),
    ("描边、分隔线", "line", "bg-line", "#E1E4E8"),
    ("控件边框", "control", "bg-control", "#767D88"),
    ("正文", "fg", "bg-fg", "#111318"),
    ("次要文字", "fg-2", "bg-fg-2", "#4A505B"),
    ("日期、署名", "fg-3", "bg-fg-3", "#5F6671"),
    ("深红", "primary", "bg-primary", "#A4161A"),
    ("深红悬停", "primary-hover", "bg-primary-hover", "#861116"),
    ("红色文字", "primary-text", "bg-primary-text", "#A4161A"),
    ("红色标签底", "primary-soft", "bg-primary-soft", "#FCE8E8"),
    ("红色标签字", "on-primary-soft", "bg-on-primary-soft", "#7A0F13"),
    ("通过", "ok", "bg-ok", "#1F7A45"),
    ("通过底", "ok-soft", "bg-ok-soft", "#E3F3E8"),
    ("提醒", "warn", "bg-warn", "#8A5A00"),
    ("提醒底", "warn-soft", "bg-warn-soft", "#FBF0D9"),
    ("信息", "info", "bg-info", "#2B5F96"),
    ("信息底", "info-soft", "bg-info-soft", "#E5EEF8"),
    ("操作提示底", "toast", "bg-toast", "#1C1F25"),
    ("操作提示字", "on-toast", "bg-on-toast", "#F2F3F5"),
    ("首屏深底", "night", "bg-night", "#0E1014"),
    ("图片卡深底", "night-2", "bg-night-2", "#20242B"),
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
    "chat",
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
