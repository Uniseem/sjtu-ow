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


# --- 「通知全体成员」 (design 10.4, v6.19) -----------------------------------

ANNOUNCE_WHY = "你收到这封邮件，是因为你在社区开着「活动通知」。"


def _moment(value) -> str:
    from django.utils.timezone import localtime

    return f"{localtime(value):%Y-%m-%d %H:%M}"


def new_tournament_letter(tournament, unsubscribe: str = "") -> Letter:
    from django.utils import timezone

    if tournament.registration_opens_at > timezone.now():
        lead = (
            f"社团发布了新的赛事「{tournament.title}」，"
            f"{_moment(tournament.registration_opens_at)} 开始报名。"
        )
    else:
        lead = f"社团发布了新的赛事「{tournament.title}」，现在可以报名了。"
    facts = []
    if tournament.starts_at:
        facts.append(("比赛时间", _moment(tournament.starts_at)))
    facts.append(("报名截止", _moment(tournament.registration_closes_at)))
    facts.append(("报名方式", tournament.get_registration_mode_display()))
    if tournament.sjtu_only:
        facts.append(("参赛范围", "仅限交大成员"))
    return Letter(
        subject=f"新赛事：{tournament.title}",
        lead=lead,
        facts=facts,
        paragraphs=[tournament.summary] if tournament.summary else [],
        action=("查看并报名", site_url(tournament.get_absolute_url())),
        reason=ANNOUNCE_WHY,
        unsubscribe=unsubscribe,
    )
