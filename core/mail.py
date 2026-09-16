"""Queued mail, SMTP from SiteSettings, and test-email sending (design 3.6 / 10.1)."""

from __future__ import annotations

import logging
from email.utils import formataddr
from html import escape

from django.conf import settings
from django.core.mail import EmailMessage, EmailMultiAlternatives, get_connection
from django.core.mail.backends.base import BaseEmailBackend
from django.core.mail.backends.smtp import EmailBackend as SMTPEmailBackend
from django.db import transaction
from django.utils.html import strip_tags

logger = logging.getLogger("sjtu_ow.mail")

DEFAULT_SUBJECT_PREFIX = "[SJTU OW]"
DEFAULT_FROM_NAME = "SJTU 守望先锋社区"


class SMTPNotConfigured(Exception):
    """Raised when SiteSettings does not have enough SMTP data to send mail."""

    def __str__(self) -> str:
        return (
            "后台尚未配置 SMTP，无法发信。"
            "请在「设置 → 全站设置」中填写 SMTP 服务器和发件地址。"
        )


def _load_site_settings():
    from core.models import SiteSettings

    try:
        return SiteSettings.load()
    except Exception:  # noqa: BLE001 — settings table may not exist yet
        return None


def get_subject_prefix() -> str:
    site = _load_site_settings()
    if site and site.email_subject_prefix:
        return site.email_subject_prefix.strip()
    return DEFAULT_SUBJECT_PREFIX


def get_from_email() -> str:
    site = _load_site_settings()
    if site and site.from_address:
        name = site.from_name or DEFAULT_FROM_NAME
        return formataddr((name, site.from_address))
    return getattr(settings, "DEFAULT_FROM_EMAIL", "noreply@localhost")


def apply_subject_prefix(subject: str, prefix: str | None = None) -> str:
    prefix = (prefix if prefix is not None else get_subject_prefix()).strip()
    subject = subject or ""
    if not prefix:
        return subject
    if subject.startswith(prefix):
        return subject
    return f"{prefix} {subject}".strip()


def _html_from_text(text: str) -> str:
    paragraphs = [
        f"<p>{escape(part)}</p>" for part in (text or "").split("\n\n") if part.strip()
    ]
    return "\n".join(paragraphs) or "<p></p>"


def ensure_text_and_html(message: EmailMessage) -> EmailMultiAlternatives:
    """Guarantee both a text body and an HTML alternative (design 10.1)."""
    alternatives = list(getattr(message, "alternatives", []) or [])
    html_parts = [content for content, mime in alternatives if mime == "text/html"]
    text_body = message.body or ""
    if not text_body and html_parts:
        text_body = strip_tags(html_parts[0])
    html_body = html_parts[0] if html_parts else _html_from_text(text_body)
    multipart = EmailMultiAlternatives(
        subject=message.subject,
        body=text_body,
        from_email=message.from_email,
        to=list(message.to or []),
        cc=list(message.cc or []),
        bcc=list(message.bcc or []),
        reply_to=list(message.reply_to or []),
        headers=dict(message.extra_headers or {}),
    )
    multipart.attach_alternative(html_body, "text/html")
    return multipart


def serialize_email(message: EmailMessage) -> dict:
    alternatives = [
        {"content": content, "mimetype": mimetype}
        for content, mimetype in getattr(message, "alternatives", []) or []
        if mimetype != "text/html"
    ]
    html_parts = [
        content
        for content, mimetype in getattr(message, "alternatives", []) or []
        if mimetype == "text/html"
    ]
    prepared = ensure_text_and_html(message)
    html_body = html_parts[0] if html_parts else prepared.alternatives[0][0]
    return {
        "subject": message.subject,
        "body": prepared.body,
        "html": html_body,
        "from_email": message.from_email,
        "to": list(message.to or []),
        "cc": list(message.cc or []),
        "bcc": list(message.bcc or []),
        "reply_to": list(message.reply_to or []),
        "extra_headers": dict(message.extra_headers or {}),
        "alternatives": alternatives,
    }


def deserialize_email(payload: dict) -> EmailMultiAlternatives:
    message = EmailMultiAlternatives(
        subject=payload.get("subject") or "",
        body=payload.get("body") or "",
        from_email=payload.get("from_email") or get_from_email(),
        to=list(payload.get("to") or []),
        cc=list(payload.get("cc") or []),
        bcc=list(payload.get("bcc") or []),
        reply_to=list(payload.get("reply_to") or []),
        headers=dict(payload.get("extra_headers") or {}),
    )
    html = payload.get("html")
    if html:
        message.attach_alternative(html, "text/html")
    for item in payload.get("alternatives") or []:
        message.attach_alternative(item["content"], item["mimetype"])
    return ensure_text_and_html(message)


def _apply_allowlist(message: EmailMessage) -> bool:
    allowlist = [
        item.lower() for item in (getattr(settings, "EMAIL_ALLOWLIST", []) or [])
    ]
    if not allowlist:
        return True

    def keep(addresses: list[str]) -> list[str]:
        return [addr for addr in addresses if addr.lower() in allowlist]

    message.to = keep(list(message.to or []))
    message.cc = keep(list(message.cc or []))
    message.bcc = keep(list(message.bcc or []))
    if not (message.to or message.cc or message.bcc):
        logger.warning("邮件被 EMAIL_ALLOWLIST 跳过：收件人不在名单中")
        return False
    return True


def build_smtp_backend(site) -> SMTPEmailBackend:
    if not site or not site.smtp_host or not site.from_address:
        raise SMTPNotConfigured
    password = site.smtp_password or None
    use_ssl = site.smtp_security == site.SmtpSecurity.SSL
    use_tls = site.smtp_security == site.SmtpSecurity.STARTTLS
    return SMTPEmailBackend(
        host=site.smtp_host,
        port=site.smtp_port,
        username=site.smtp_username or None,
        password=password or None,
        use_tls=use_tls,
        use_ssl=use_ssl,
        fail_silently=False,
    )


class SiteSettingsEmailBackend(BaseEmailBackend):
    """Send using SMTP stored in SiteSettings, not environment variables."""

    def send_messages(self, email_messages):
        site = _load_site_settings()
        connection = build_smtp_backend(site)
        prepared = []
        for message in email_messages:
            message = ensure_text_and_html(message)
            if not _apply_allowlist(message):
                continue
            message.subject = apply_subject_prefix(message.subject)
            if site.from_address:
                message.from_email = formataddr(
                    (site.from_name or DEFAULT_FROM_NAME, site.from_address)
                )
            prepared.append(message)
        if not prepared:
            return 0
        return connection.send_messages(prepared)


def deliver_email_payload(payload: dict) -> int:
    """Used by the worker: send a serialized message via EMAIL_DELIVERY_BACKEND."""
    message = deserialize_email(payload)
    message.subject = apply_subject_prefix(message.subject)
    site = _load_site_settings()
    if site and site.from_address and not message.from_email:
        message.from_email = formataddr(
            (site.from_name or DEFAULT_FROM_NAME, site.from_address)
        )
    if not _apply_allowlist(message):
        return 0
    backend = getattr(
        settings,
        "EMAIL_DELIVERY_BACKEND",
        "django.core.mail.backends.smtp.EmailBackend",
    )
    if backend == "core.mail.SiteSettingsEmailBackend":
        connection = SiteSettingsEmailBackend(fail_silently=False)
    else:
        connection = get_connection(backend=backend, fail_silently=False)
    return connection.send_messages([message])


def send_test_email(to_email: str) -> None:
    """Synchronous SMTP test for the admin button (does not use the queue)."""
    site = _load_site_settings()
    connection = build_smtp_backend(site)
    prefix = get_subject_prefix()
    subject = apply_subject_prefix("SMTP 测试邮件", prefix)
    text = (
        "这是一封来自上海交通大学守望先锋社区后台的测试邮件。"
        "如果你能读到它，说明 SMTP 配置可用。"
    )
    message = EmailMultiAlternatives(
        subject=subject,
        body=text,
        from_email=get_from_email(),
        to=[to_email],
    )
    message.attach_alternative(_html_from_text(text), "text/html")
    sent = connection.send_messages([message])
    if not sent:
        raise RuntimeError("SMTP 服务器没有接受这封测试邮件。")


class QueuedEmailBackend(BaseEmailBackend):
    """Django EMAIL_BACKEND: enqueue, then the worker delivers (design 10.1)."""

    def send_messages(self, email_messages):
        from core.tasks import deliver_queued_email

        payloads = [serialize_email(message) for message in email_messages]

        def enqueue() -> None:
            for payload in payloads:
                deliver_queued_email.enqueue(payload)

        if transaction.get_connection().in_atomic_block:
            transaction.on_commit(enqueue)
        else:
            enqueue()
        return len(payloads)
