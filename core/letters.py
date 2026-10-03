"""Every email the site writes is a letter (design 10.3, v5.4).

A ``Letter`` holds what one message says: the subject, the conclusion first,
then details, the key facts as a small table, at most one thing to do, and
why this person is getting it. ``render`` turns it into the plain text and the
HTML, both with the greeting, 「祝好！」, the signature and the date; ``send``
writes one message per address so nobody sees anyone else's.

Subjects stay bare: ``core.mail`` adds the site's prefix on the way out (10.1).
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass, field
from urllib.parse import urlsplit

from django.conf import settings
from django.core.mail import EmailMultiAlternatives
from django.template.loader import render_to_string
from django.utils import timezone

logger = logging.getLogger("sjtu_ow.mail")

CLOSING = "祝好！"
SIGNATURE = "上海交通大学守望先锋社区"
NO_REPLY = "这封邮件由系统自动发送，请不要直接回复。"


@dataclass
class Letter:
    subject: str
    lead: str  # the first paragraph: what happened
    paragraphs: list[str] = field(default_factory=list)
    facts: list[tuple[str, str]] = field(default_factory=list)
    items: list[tuple[str, str]] = field(default_factory=list)  # (text, url)
    item_link: str = "打开"  # the words on each item's link
    code: str = ""  # a verification code, shown large
    action: tuple[str, str] | None = None  # (button label, absolute url)
    note: str = ""  # small print after the button
    reason: str = ""  # footer: why this person gets it
    # Only on mail people may turn off (design 10.4): the footer links to it
    # and the message carries List-Unsubscribe for mail clients.
    unsubscribe: str = ""


def site_url(path: str = "/") -> str:
    base = (getattr(settings, "SITE_URL", "") or "").rstrip("/")
    return base + path


def site_host() -> str:
    return urlsplit(site_url("/")).netloc or site_url("/")


def greeting(name: str = "") -> str:
    """「昵称，你好：」; 「你好：」 when we do not know who it is."""
    return f"{name}，你好：" if name else "你好："


def dated() -> str:
    today = timezone.localdate()
    return f"{today.year} 年 {today.month} 月 {today.day} 日"


def frame(name: str = "", *, subject: str = "", preheader: str = "") -> dict:
    """What every letter's frame prints, for our templates and allauth's."""
    return {
        "subject": subject,
        "preheader": preheader,
        "greeting": greeting(name),
        "closing": CLOSING,
        "signature": SIGNATURE,
        "date": dated(),
        "no_reply": NO_REPLY,
        "site_url": site_url("/"),
        "site_host": site_host(),
    }


def text_of(letter: Letter, name: str = "") -> str:
    parts = [greeting(name), letter.lead]
    if letter.facts:
        parts.append("\n".join(f"{label}：{value}" for label, value in letter.facts))
    if letter.code:
        parts.append(f"验证码：{letter.code}")
    if letter.items:
        parts.append(
            "\n".join(
                f"- {text}" + (f"\n  {url}" if url else "")
                for text, url in letter.items
            )
        )
    parts.extend(letter.paragraphs)
    if letter.action:
        label, url = letter.action
        parts.append(f"{label}：{url}")
    if letter.note:
        parts.append(letter.note)
    parts.append(CLOSING)
    parts.append(f"{SIGNATURE}\n{dated()}")
    unsubscribe = f"\n退订活动通知：{letter.unsubscribe}" if letter.unsubscribe else ""
    parts.append(f"——\n{letter.reason}{NO_REPLY}{unsubscribe}\n{site_url('/')}")
    return "\n\n".join(part for part in parts if part)


def html_of(letter: Letter, name: str = "") -> str:
    context = frame(name, subject=letter.subject, preheader=letter.lead)
    context["letter"] = letter
    return render_to_string("email/letter.html", context)


def render(letter: Letter, name: str = "") -> tuple[str, str]:
    return text_of(letter, name), html_of(letter, name)


def message(letter: Letter, address: str, name: str = "") -> EmailMultiAlternatives:
    text, html = render(letter, name)
    headers = {}
    if letter.unsubscribe:
        # RFC 8058: the mail client's own 「退订」 posts to this address.
        headers = {
            "List-Unsubscribe": f"<{letter.unsubscribe}>",
            "List-Unsubscribe-Post": "List-Unsubscribe=One-Click",
        }
    email = EmailMultiAlternatives(
        subject=letter.subject, body=text, to=[address], headers=headers
    )
    email.attach_alternative(html, "text/html")
    return email


def people(recipients) -> list[tuple[str, str]]:
    """(address, name) once per address. Users bring their nickname; a bare
    address is looked up so admins are greeted by name too."""
    from accounts.models import User

    found: dict[str, str] = {}
    bare = []
    for recipient in recipients:
        if isinstance(recipient, str):
            if recipient:
                bare.append(recipient)
            continue
        address = getattr(recipient, "email", "")
        if address and address not in found:
            found[address] = getattr(recipient, "nickname", "") or ""
    if bare:
        names = dict(
            User.objects.filter(email__in=bare).values_list("email", "nickname")
        )
        for address in bare:
            found.setdefault(address, names.get(address, ""))
    return sorted(found.items())


def send(letter: Letter, recipients, *, fail_silently: bool = False) -> int:
    """One message per address, each greeted by name (design 10.1, 10.3)."""
    sent = 0
    for address, name in people(recipients):
        sent += message(letter, address, name).send(fail_silently=fail_silently)
    return sent


# --- mail written elsewhere (Wagtail's notifications) ----------------------------

URL = re.compile(r"https?://[^\s<>\"'）」]+")


def wrap_text(text: str, subject: str = "") -> str:
    """HTML for a message that only has plain text: the same frame, the text's
    own paragraphs inside, links made clickable. The text already carries its
    greeting and closing, so the frame adds neither."""
    from django.utils.safestring import mark_safe

    body, _rule, foot = text.strip().partition("\n——\n")
    blocks = [
        mark_safe(_lines_html(block))
        for block in re.split(r"\n\s*\n", body)
        if block.strip()
    ]
    first = re.split(r"\n\s*\n", body, maxsplit=1)[0]
    context = frame(subject=subject, preheader=first.strip())
    context["blocks"] = blocks
    # What follows the text's own 「——」 (why you got it, no reply) is the
    # frame's footer, so it is not said twice.
    context["foot"] = mark_safe(_lines_html(foot)) if foot.strip() else ""
    return render_to_string("email/plain.html", context)


def _link(match) -> str:
    url = match.group(0)
    return f'<a href="{url}" style="color:inherit;">{url}</a>'


def _lines_html(block: str) -> str:
    from django.utils.html import escape

    return "<br>".join(
        URL.sub(_link, escape(line.strip()))
        for line in block.splitlines()
        if line.strip()
    )
