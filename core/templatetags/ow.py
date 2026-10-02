"""Template filters for the design system's fixed formats (design 13.2.4).

Dates, times, weekdays, numbering and slot meters are formatted here once so
every page prints them the same way.
"""

from __future__ import annotations

from datetime import date, datetime

from django import template
from django.utils import timezone
from django.utils.html import format_html, format_html_join

register = template.Library()

WEEKDAYS = "一二三四五六日"


def _local(value):
    if isinstance(value, datetime):
        if timezone.is_aware(value):
            return timezone.localtime(value)
        return value
    return value


@register.filter
def ow_date(value) -> str:
    """``2026.09.28``."""
    if not isinstance(value, (date, datetime)):
        return ""
    return _local(value).strftime("%Y.%m.%d")


@register.filter
def ow_md(value) -> str:
    """``09.28`` — for lists that stay within one year."""
    if not isinstance(value, (date, datetime)):
        return ""
    return _local(value).strftime("%m.%d")


@register.filter
def ow_time(value) -> str:
    """``19:30``, 24-hour clock."""
    if not isinstance(value, datetime):
        return ""
    return _local(value).strftime("%H:%M")


@register.filter
def ow_weekday(value) -> str:
    """``周五``."""
    if not isinstance(value, (date, datetime)):
        return ""
    return "周" + WEEKDAYS[_local(value).weekday()]


@register.filter
def ow_index(value) -> str:
    """Two-digit numbering: ``01``, ``02`` … ``10``."""
    try:
        return f"{int(value):02d}"
    except (TypeError, ValueError):
        return ""


@register.filter
def initial(value) -> str:
    """The first Chinese character or letter of a name, for avatars; leading
    symbols, emoji and spaces are skipped; "?" when there is none
    (design-details 2.2)."""
    for char in str(value or ""):
        if char.isalnum():
            return char.upper()
    return "?"


AVATAR_HUES = 5


@register.filter
def hue(obj) -> int:
    """One of the five tints (1–5) for a face or logo without a picture,
    fixed by id so a person or team keeps its colour everywhere
    (design-details 1.5)."""
    return (getattr(obj, "pk", None) or 0) % AVATAR_HUES + 1


MOST_SEATS = 24


@register.simple_tag
def seats(taken, total) -> list[bool]:
    """One cell per place, taken first (v6.0 draft c-seats). A game rarely
    needs more than 12; past MOST_SEATS each cell stands for a share, so the
    row never runs to dozens of slivers."""
    try:
        taken, total = max(int(taken or 0), 0), max(int(total or 0), 0)
    except (TypeError, ValueError):
        return []
    if total == 0:
        return []
    cells = min(total, MOST_SEATS)
    filled = min(cells, round(taken * cells / total))
    return [index < filled for index in range(cells)]


@register.filter
def member_url(user) -> str:
    """The person's own page (design 6.4), or "" for someone who no longer
    has one (deactivated), so a template can leave the name unlinked."""
    from members.services import member_url as url

    if user is None or not getattr(user, "is_active", False):
        return ""
    return url(user)


@register.filter
def hue_scene(obj) -> str:
    """The static address of an object's base picture (design-details 2.2)."""
    from django.templatetags.static import static

    from core import placeholders

    return static(f"{placeholders.DIRECTORY}/{placeholders.hue_filename(hue(obj))}")


@register.filter
def public_profile(user):
    """Positions and ranks as the public pages show them (design-details 3)."""
    from accounts.roles import public_profile as profile

    return profile(user)


@register.filter
def rank_parts(label) -> tuple[str, str]:
    """``"钻石 3"`` → (``"钻石"``, ``"3"``); ``"前 500"`` → (``"前"``, ``"500"``)."""
    text = str(label or "").strip()
    name, _, number = text.partition(" ")
    return name, number


@register.filter
def lookup(mapping, key):
    """``{{ counts|lookup:item.pk }}``; missing keys give None."""
    try:
        return mapping.get(key)
    except AttributeError:
        return None


@register.simple_tag(takes_context=True)
def section_picture(context, section, css_class) -> str:
    """The picture behind the hero or a section's page head (13.2.5, v5.1):
    the 首屏图片 or 栏目横幅 uploaded in 全站设置, else the place's own moving
    scene twice, by day and at night; the stylesheet shows the one for the
    current mode (c-scene--light / c-scene--dark)."""
    from django.templatetags.static import static

    from core import placeholders
    from core.models import SiteSettings

    # The request already holds the settings (context processors): no query.
    site = SiteSettings.load(request_or_site=context.get("request"))
    if section == "home":
        image, spec, size = site.hero_image, "fill-2400x1350-c50", (2400, 1350)
    else:
        image, spec, size = (
            getattr(site, f"banner_{section}"), "fill-2400x640-c50", (2400, 640)
        )  # fmt: skip
    tag = '<img class="{}" src="{}" alt="" width="{}" height="{}">'
    if image is not None:
        return format_html(tag, css_class, image.get_rendition(spec).url, *size)
    paths = placeholders.section_paths(section)
    return format_html_join(
        "",
        tag,
        (
            (f"{css_class} c-scene c-scene--{mode}", static(paths[mode]), *size)
            for mode in ("light", "dark")
        ),
    )


@register.filter
def cover_placeholder(obj) -> str:
    """The picture an article or tournament shows without a cover (13.2.5).

    Always the same one for the same object, so its card and its page agree.
    """
    from django.templatetags.static import static

    from core import placeholders

    return static(placeholders.static_path(obj))
