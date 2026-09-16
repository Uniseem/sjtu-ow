"""Tournament emails (design 8.1). One message per recipient."""

from __future__ import annotations

from django.conf import settings
from django.core.mail import send_mail


def site_url(path: str) -> str:
    base = getattr(settings, "SITE_URL", "") or ""
    return base.rstrip("/") + path


def tournament_cancelled(tournament, captain, reason="") -> None:
    if not getattr(captain, "email", ""):
        return
    body = (
        f"赛事「{tournament.title}」已取消。\n\n"
        f"{('说明：' + reason) if reason else ''}\n"
        f"赛事页面：{site_url(tournament.get_absolute_url())}"
    )
    send_mail(
        subject="赛事已取消",
        message=body,
        from_email=None,
        recipient_list=[captain.email],
        fail_silently=False,
    )


def registration_submitted(registration, action) -> None:
    from tournaments.notifications_registration import registration_submitted as impl

    impl(registration, action)


def registration_status_changed(registration, note="") -> None:
    from tournaments.notifications_registration import (
        registration_status_changed as impl,
    )

    impl(registration, note)
