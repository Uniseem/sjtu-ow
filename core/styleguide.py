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
    ("交大红", "primary", "bg-primary", "#B2141A"),
    ("深红", "primary-deep", "bg-primary-deep", "#861116"),
    ("主色容器", "primary-container", "bg-primary-container", "#FFDAD5"),
    ("主色容器的字", "on-primary-container", "bg-on-primary-container", "#410002"),
    ("第三色容器", "tertiary-container", "bg-tertiary-container", "#FBDFA6"),
    ("第三色容器的字", "on-tertiary-container", "bg-on-tertiary-container", "#251A00"),
    ("页面", "surface", "bg-surface", "#FFF8F7"),
    ("卡片", "surface-lowest", "bg-surface-lowest", "#FFFFFF"),
    ("页脚", "surface-low", "bg-surface-low", "#FFF0EE"),
    ("色调区块", "surface-mid", "bg-surface-mid", "#FCEAE7"),
    ("表头、占位", "surface-high", "bg-surface-high", "#F6E4E2"),
    ("进度条底", "surface-highest", "bg-surface-highest", "#F1DEDC"),
    ("正文", "on-surface", "bg-on-surface", "#231918"),
    ("次要文字", "on-surface-2", "bg-on-surface-2", "#534341"),
    ("第三级文字", "on-surface-3", "bg-on-surface-3", "#6B5A58"),
    ("控件边框", "outline", "bg-outline", "#857371"),
    ("描边、分隔线", "outline-variant", "bg-outline-variant", "#D8C2BF"),
    ("提示条底", "inverse-surface", "bg-inverse-surface", "#392E2C"),
    ("提示条字", "inverse-on-surface", "bg-inverse-on-surface", "#FBEEEC"),
    ("提示条红", "inverse-primary", "bg-inverse-primary", "#FFB4A9"),
    ("通过", "ok", "bg-ok", "#2F6F45"),
    ("通过底", "ok-container", "bg-ok-container", "#D7EEDD"),
    ("提醒", "warn", "bg-warn", "#7A4F00"),
    ("提醒底", "warn-container", "bg-warn-container", "#FBDFA6"),
    ("信息", "info", "bg-info", "#3F6789"),
    ("信息底", "info-container", "bg-info-container", "#DCECF9"),
    ("磁贴·玫瑰", "tile-rose", "bg-tile-rose", "#FFE6E1"),
    ("磁贴·奶油", "tile-butter", "bg-tile-butter", "#FDF1D6"),
    ("磁贴·淡紫", "tile-lilac", "bg-tile-lilac", "#F2E7F8"),
    ("磁贴·天蓝", "tile-sky", "bg-tile-sky", "#E3EEF8"),
    ("磁贴·粉", "tile-blush", "bg-tile-blush", "#FBE6EF"),
    ("磁贴·薄荷", "tile-mint", "bg-tile-mint", "#E4F1E9"),
    ("图标片·奶油", "chip-butter", "bg-chip-butter", "#705C2E"),
    ("图标片·淡紫", "chip-lilac", "bg-chip-lilac", "#6E4F86"),
    ("图标片·天蓝", "chip-sky", "bg-chip-sky", "#3D6A8A"),
    ("图标片·粉", "chip-blush", "bg-chip-blush", "#8E3A62"),
    ("图标片·薄荷", "chip-mint", "bg-chip-mint", "#3B6B52"),
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
