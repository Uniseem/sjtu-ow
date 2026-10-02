"""The design-system specimen page, /_styleguide/ (design 13.2.7).

Every component in every state on one page, with made-up sample data — no
database reads. Only people who can enter the admin see it; everyone else
gets a 404 so the page does not advertise itself.
"""

from __future__ import annotations

from datetime import datetime, timedelta

from django.http import Http404, HttpResponse
from django.shortcuts import render
from django.utils import timezone
from django.utils.csp import CSP
from django.views.decorators.clickjacking import xframe_options_sameorigin
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
    ("砖红", "primary", "bg-primary", "#9B3A33"),
    ("砖红悬停", "primary-hover", "bg-primary-hover", "#80302A"),
    ("红色文字", "primary-text", "bg-primary-text", "#963830"),
    ("红色标签底", "primary-soft", "bg-primary-soft", "#F1E0DA"),
    ("红色标签字", "on-primary-soft", "bg-on-primary-soft", "#73291F"),
    ("通过", "ok", "bg-ok", "#3B6D4F"),
    ("通过底", "ok-soft", "bg-ok-soft", "#DFE9E0"),
    ("沙杏（守望先锋橙收淡）", "accent", "bg-accent", "#CF9152"),
    ("橙色小字", "accent-text", "bg-accent-text", "#8D5219"),
    ("橙色大字", "accent-display", "bg-accent-display", "#A86C30"),
    ("橙色标签底", "accent-soft", "bg-accent-soft", "#F3E3CD"),
    ("橙色标签字", "on-accent-soft", "bg-on-accent-soft", "#6B3D12"),
    ("提醒", "warn", "bg-warn", "#685513"),
    ("提醒底", "warn-soft", "bg-warn-soft", "#EFE7C7"),
    ("信息", "info", "bg-info", "#3A5F82"),
    ("信息底", "info-soft", "bg-info-soft", "#E0E8EF"),
    ("操作提示底", "toast", "bg-toast", "#1C1F25"),
    ("操作提示字", "on-toast", "bg-on-toast", "#F2F3F5"),
    # Inside the night bands (13.2.6 深色条): the dark mode's values.
    ("深色条底", "night", "bg-night", "#141A24"),
    ("图片卡深底", "night-2", "bg-night-2", "#222A37"),
    ("深色条里的深红", "night-accent", "bg-night-accent", "#A8463D"),
    ("深色条卡片", "night-surface", "bg-night-surface", "#1A2130"),
    ("深色条分隔线", "night-line", "bg-night-line", "#2D3646"),
    ("深色条控件边框", "night-control", "bg-night-control", "#6E7889"),
    ("深色条正文", "night-fg", "bg-night-fg", "#E8EAEE"),
    ("深色条次要文字", "night-fg-2", "bg-night-fg-2", "#B6BCC7"),
    ("深色条日期", "night-fg-3", "bg-night-fg-3", "#959CAB"),
    ("深色条红字", "night-primary-text", "bg-night-primary-text", "#EE9A90"),
    ("深色条红标签底", "night-primary-soft", "bg-night-primary-soft", "#3A2226"),
    ("深色条红标签字", "night-on-primary-soft", "bg-night-on-primary-soft", "#F5C3BC"),
    ("深色条橙标签底", "night-accent-soft", "bg-night-accent-soft", "#3A2D1C"),
    ("深色条橙标签字", "night-on-accent-soft", "bg-night-on-accent-soft", "#F0CB98"),
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
    from core import placeholders

    now = timezone.localtime()
    base = now.replace(hour=19, minute=30, second=0, microsecond=0)
    return {
        "colours": COLOURS,
        "statuses": STATUSES,
        "icons": ICONS,
        "placeholders": placeholders.catalogue(),
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


def _admins_only(request):
    user = request.user
    if not (user.is_authenticated and user.has_perm(ADMIN_PERMISSION)):
        raise Http404


@require_GET
def styleguide(request):
    _admins_only(request)
    return render(request, "core/styleguide.html", sample_context())


# Email HTML is inline styles throughout (design 10.3), which the site's policy
# forbids; one email on its own may use them, and only this site may frame it.
EMAIL_CSP = {
    "default-src": [CSP.NONE],
    "style-src": [CSP.UNSAFE_INLINE],
    "img-src": [CSP.SELF, "data:"],
    "frame-ancestors": [CSP.SELF],
    "base-uri": [CSP.NONE],
    "form-action": [CSP.NONE],
}


@require_GET
def styleguide_emails(request):
    """Every email the site sends, with sample data (design 10.3)."""
    from core.email_samples import samples

    _admins_only(request)
    return render(request, "core/styleguide_emails.html", {"samples": samples()})


@require_GET
@xframe_options_sameorigin
def styleguide_email(request, key):
    """One email's HTML exactly as it is sent, for the frames on that page."""
    from core.email_samples import sample

    _admins_only(request)
    found = sample(key)
    if found is None:
        raise Http404
    response = HttpResponse(found.html)
    response._csp_config = EMAIL_CSP
    return response
