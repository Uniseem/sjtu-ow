"""Tournament emails (design 8.1), written as letters (10.3). One per person.

``*_letter`` builds what an email says; the function without the suffix
sends it (see teams.notifications).
"""

from __future__ import annotations

from core.letters import Letter, send, site_url


def tournament_cancelled_letter(tournament, reason="") -> Letter:
    return Letter(
        subject=f"赛事已取消：{tournament.title}",
        lead=f"「{tournament.title}」已经取消，你的报名不再有效。",
        facts=[("说明", reason)] if reason else [],
        paragraphs=["给你带来不便，抱歉。之后有新的赛事会在网站上公布。"],
        action=("查看赛事页面", site_url(tournament.get_absolute_url())),
        reason=f"你收到这封邮件，是因为你报名了「{tournament.title}」。",
    )


def tournament_cancelled(tournament, captain, reason="") -> None:
    send(tournament_cancelled_letter(tournament, reason), [captain])


def registration_submitted(registration, action) -> None:
    from tournaments.notifications_registration import registration_submitted as impl

    impl(registration, action)


def registration_status_changed(registration, note="") -> None:
    from tournaments.notifications_registration import (
        registration_status_changed as impl,
    )

    impl(registration, note)
