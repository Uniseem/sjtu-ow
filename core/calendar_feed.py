"""「订阅到手机日历」 (design 13.5, v6.49): a member's signed-up scrims and
tournaments as an iCalendar feed their phone polls. No login, like the
unsubscribe link: the address carries a signature over the user's id.
"""

from __future__ import annotations

from datetime import timedelta

from django.core import signing
from django.urls import reverse
from django.utils import timezone

CALENDAR_SALT = "sjtu-ow.calendar"
LENGTHS = {"内战": timedelta(hours=3), "赛事": timedelta(hours=4)}


def token(user) -> str:
    return signing.dumps(user.pk, salt=CALENDAR_SALT)


def user_for(raw: str):
    from accounts.models import User

    try:
        pk = signing.loads(raw, salt=CALENDAR_SALT)
    except signing.BadSignature:
        return None
    return User.objects.filter(pk=pk, is_active=True).first()


def feed_url(user, *, webcal=False) -> str:
    from core.letters import site_url

    url = site_url(reverse("calendar_feed", args=[token(user)]))
    if webcal:
        return "webcal://" + url.split("://", 1)[-1]
    return url


def _escape(text: str) -> str:
    return (
        text.replace("\\", "\\\\")
        .replace(";", "\\;")
        .replace(",", "\\,")
        .replace("\n", "\\n")
    )


def _fold(line: str) -> str:
    """RFC 5545 3.1: a line longer than 75 octets goes on over the next
    lines, each starting with a space, without splitting a character."""
    parts, current, size = [], "", 0
    for char in line:
        width = len(char.encode())
        if size + width > 75:
            parts.append(current)
            current, size = " ", 1
        current += char
        size += width
    parts.append(current)
    return "\r\n".join(parts)


def _stamp(moment) -> str:
    return timezone.localtime(moment, timezone.UTC).strftime("%Y%m%dT%H%M%SZ")


def ics(user, now=None) -> str:
    from core.agenda import items_for
    from core.letters import site_url

    now = now or timezone.now()
    host = site_url("/").split("://", 1)[-1].strip("/") or "sjtu-ow"
    lines = [
        "BEGIN:VCALENDAR",
        "VERSION:2.0",
        "PRODID:-//SJTU OW//sjtu-ow//ZH",
        "CALSCALE:GREGORIAN",
        f"X-WR-CALNAME:{_escape(f'{user.nickname} 的社团安排')}",
        "X-WR-TIMEZONE:Asia/Shanghai",
    ]
    for item in items_for(user, now=now, limit=None):
        if item.when is None:
            continue  # a calendar cannot hold an event without a time
        url = site_url(item.url)
        lines += [
            "BEGIN:VEVENT",
            f"UID:{_escape(item.url.strip('/').replace('/', '-'))}@{host}",
            f"DTSTAMP:{_stamp(now)}",
            f"DTSTART:{_stamp(item.when)}",
            f"DTEND:{_stamp(item.when + LENGTHS.get(item.kind, timedelta(hours=3)))}",
            f"SUMMARY:{_escape(f'{item.kind}：{item.title}')}",
            f"DESCRIPTION:{_escape(f'{item.note}\n{url}')}",
            f"URL:{url}",
            "END:VEVENT",
        ]
    lines.append("END:VCALENDAR")
    return "\r\n".join(_fold(line) for line in lines) + "\r\n"
