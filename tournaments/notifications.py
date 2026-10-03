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


def contact_fact(tournament) -> list:
    """Design 8.1 (v6.32): letters to people taking part carry the contact."""
    contact = getattr(tournament, "participant_contact", "")
    return [("选手联系方式", contact)] if contact else []


def moment(value) -> str:
    from django.utils.timezone import localtime

    return f"{localtime(value):%Y-%m-%d %H:%M}"


def time_changed_letter(tournament, old_starts_at) -> Letter:
    """Design 8.1 (v6.34): the start moved; say from when to when."""
    return Letter(
        subject=f"比赛时间改了：{tournament.title}",
        lead=(
            f"「{tournament.title}」的比赛时间改了："
            f"原来 {moment(old_starts_at)}，现在 {moment(tournament.starts_at)}。"
        ),
        facts=[
            ("现在的时间", moment(tournament.starts_at)),
            *contact_fact(tournament),
        ],
        paragraphs=[
            "开赛前会按新的时间再提醒一次。新时间来不了的话，请尽早告诉队长或赛事管理员。"
        ],
        action=("查看赛事页面", site_url(tournament.get_absolute_url())),
        reason=f"你收到这封邮件，是因为你报名了「{tournament.title}」。",
    )


def participants(tournament) -> list:
    """Everyone taking part (design 8.1): live rosters and the pool, once each."""
    from accounts.models import User

    ids = set(
        tournament.roster_members.filter(is_active=True).values_list(
            "user_id", flat=True
        )
    ) | set(tournament.individual_signups.values_list("user_id", flat=True))
    return list(
        User.objects.filter(pk__in=ids, is_active=True).exclude(email="").order_by("pk")
    )


def time_changed(tournament, old_starts_at) -> int:
    return send(
        time_changed_letter(tournament, old_starts_at),
        participants(tournament),
        fail_silently=True,
    )


def tournament_reminder_letter(tournament, row) -> Letter:
    """Design 8.1 (v6.24): one per player, with their own team and game ID."""
    registration = row.registration
    ask = "赛事管理员" if registration.team_id is None else "队长"
    return Letter(
        subject=f"赛事提醒：{tournament.title}",
        lead=(
            f"「{tournament.title}」将在 {moment(tournament.starts_at)} 开始，"
            f"你所在的「{registration.team_name}」已通过报名。"
        ),
        facts=[
            ("比赛时间", moment(tournament.starts_at)),
            ("你的队伍", registration.team_name),
            ("你的游戏 ID", row.battletag or "未填"),
            *contact_fact(tournament),
        ],
        paragraphs=[
            f"比赛安排和规则以赛事页面为准，请提前上线。临时来不了的话，请尽早告诉{ask}。"
        ],
        action=("查看赛事页面", site_url(tournament.get_absolute_url())),
        reason=(
            f"你收到这封邮件，是因为你在「{tournament.title}」已通过报名的名单里。"
        ),
    )


def unplaced_reminder_letter(tournament) -> Letter:
    """Design 8.1 (v6.29): a pool signup nobody has placed yet, once teams
    are being formed."""
    return Letter(
        subject=f"赛事提醒：{tournament.title}",
        lead=(
            f"「{tournament.title}」将在 {moment(tournament.starts_at)} 开始，"
            "你还在散人池里，没有被编进队伍。"
        ),
        facts=[("比赛时间", moment(tournament.starts_at)), *contact_fact(tournament)],
        paragraphs=[
            "赛事管理员可能还在编队，编进队伍时你会另外收到一封邮件。"
            "到开赛还没编进的话，这次可能没有位置；有疑问请联系赛事管理员。"
        ],
        action=("查看赛事页面", site_url(tournament.get_absolute_url())),
        reason=f"你收到这封邮件，是因为你个人报名了「{tournament.title}」。",
    )


def unplaced_reminder(tournament) -> int:
    """Everyone still in the pool, one letter each."""
    sent = 0
    for signup in tournament.individual_signups.filter(
        registration__isnull=True
    ).select_related("user"):
        if not (signup.user.is_active and signup.user.email):
            continue
        sent += send(
            unplaced_reminder_letter(tournament), [signup.user], fail_silently=True
        )
    return sent


def tournament_reminder(tournament) -> int:
    """Everyone holding a place on an approved roster, one letter each."""
    from tournaments.models import RegistrationMember, RegistrationStatus

    rows = RegistrationMember.objects.filter(
        tournament=tournament,
        is_active=True,
        registration__status=RegistrationStatus.APPROVED,
    ).select_related("registration", "user")
    sent = 0
    for row in rows:
        if not (row.user.is_active and row.user.email):
            continue
        letter = tournament_reminder_letter(tournament, row)
        sent += send(letter, [row.user], fail_silently=True)
    return sent


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


def new_tournament_letter(tournament, unsubscribe: str = "") -> Letter:
    from django.utils import timezone

    if tournament.registration_opens_at > timezone.now():
        lead = (
            f"社团发布了新的赛事「{tournament.title}」，"
            f"{moment(tournament.registration_opens_at)} 开始报名。"
        )
    else:
        lead = f"社团发布了新的赛事「{tournament.title}」，现在可以报名了。"
    facts = []
    if tournament.starts_at:
        facts.append(("比赛时间", moment(tournament.starts_at)))
    facts.append(("报名截止", moment(tournament.registration_closes_at)))
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
