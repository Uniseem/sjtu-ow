"""Scrim emails (design 9.1, 10.2), written as letters (10.3). One per person.

Subjects are written bare: core.mail prefixes every outgoing message with
the site's configured prefix ([SJTU OW] by default, 附录 C), so a prefix
written here would be doubled and would ignore the admin's setting.
``*_letter`` builds what an email says; the function without the suffix
sends it (see teams.notifications).
"""

from __future__ import annotations

import logging

from django.urls import reverse
from django.utils import timezone

from core.letters import Letter, send, site_url

logger = logging.getLogger(__name__)


def _when(scrim) -> str:
    return timezone.localtime(scrim.starts_at).strftime("%Y-%m-%d %H:%M")


def _link(scrim) -> str:
    return site_url(reverse("scrim_detail", args=[scrim.pk]))


def _recipients(scrim) -> list:
    return [
        signup.user
        for signup in scrim.signups.select_related("user")
        if signup.user.is_active and signup.user.email
    ]


def _facts(scrim) -> list[tuple[str, str]]:
    return [("开始时间", _when(scrim)), ("规格", scrim.get_format_display())]


def _why(scrim) -> str:
    return f"你收到这封邮件，是因为你报名了内战「{scrim.title}」。"


def scrim_cancelled_letter(scrim) -> Letter:
    return Letter(
        subject=f"内战已取消：{scrim.title}",
        lead=f"内战「{scrim.title}」取消了，原定的时间不用再留出来。",
        facts=_facts(scrim),
        paragraphs=["之后有新的内战会在网站上公布。"],
        action=("查看活动页面", _link(scrim)),
        reason=_why(scrim),
    )


def scrim_cancelled(scrim) -> int:
    """Design 9.1: tell everyone who signed up."""
    return send(scrim_cancelled_letter(scrim), _recipients(scrim), fail_silently=True)


def scrim_reminder_letter(scrim, placement: str = "") -> Letter:
    facts = _facts(scrim)
    if placement:
        # Design 9.2 (v6.22): the player's own place, if it is set by now.
        facts = [*facts, ("你的分队", f"{placement}（以群里发的为准）")]
    return Letter(
        subject=f"内战提醒：{scrim.title}",
        lead=f"内战「{scrim.title}」就要开始了，请提前上线。",
        facts=facts,
        paragraphs=["分队结果由管理员发到群里。临时来不了的话，请尽早告诉管理员。"],
        action=("查看活动页面", _link(scrim)),
        reason=_why(scrim),
    )


def scrim_reminder(scrim) -> int:
    """Design 9.1: the reminder that goes out before it starts, one per
    player so each sees their own place (v6.22)."""
    from scrims.services import placement, split_scrim_ids

    has_split = bool(split_scrim_ids([scrim.pk]))
    sent = 0
    for signup in scrim.signups.select_related("user", "scrim"):
        if not (signup.user.is_active and signup.user.email):
            continue
        letter = scrim_reminder_letter(scrim, placement(signup, has_split=has_split))
        sent += send(letter, [signup.user], fail_silently=True)
    return sent


# --- 「通知全体成员」 (design 10.4, v6.19) -----------------------------------


def new_scrim_letter(scrim, unsubscribe: str = "") -> Letter:
    facts = [
        *_facts(scrim),
        (
            "报名截止",
            timezone.localtime(scrim.signup_deadline).strftime("%Y-%m-%d %H:%M"),
        ),
    ]
    if scrim.sjtu_only:
        facts.append(("参加范围", "仅限交大成员"))
    description = (scrim.description or "").strip()
    if len(description) > 300:
        description = description[:300] + "……"
    return Letter(
        subject=f"新内战：{scrim.title}",
        lead=f"社团发布了新的内战「{scrim.title}」，现在可以报名了。",
        facts=facts,
        paragraphs=[description] if description else [],
        action=("查看并报名", _link(scrim)),
        reason="你收到这封邮件，是因为你在社区开着「活动通知」。",
        unsubscribe=unsubscribe,
    )
