"""Emails about uploaded faces (design 10.2, design-details 2.3; v6.11),
written as letters (10.3).

``*_letter`` builds what one email says; the function next to it sends it
(see teams.notifications). The specimen page /_styleguide/emails/ renders
the builders with sample data.
"""

from __future__ import annotations

from django.urls import reverse

from core.letters import Letter, site_url
from core.outbox import hold


def _profile_url() -> str:
    return site_url(reverse("me_profile"))


def _why_owner() -> str:
    return "你收到这封邮件，是因为你在社区上传过头像。"


def _review_facts(submission) -> list[tuple[str, str]]:
    facts = [("原因", submission.get_reason_display() or "（未填写）")]
    if submission.note:
        facts.append(("说明", submission.note))
    return facts


def avatar_taken_down_letter(submission) -> Letter:
    return Letter(
        subject="你的头像已被撤下",
        lead="你正在用的头像被管理员撤下了，现在显示的是默认头像。",
        facts=_review_facts(submission),
        paragraphs=["那张图已经删除。你可以换一张重新上传。"],
        action=("重新上传", _profile_url()),
        reason=_why_owner(),
    )


def avatar_taken_down(submission) -> None:
    hold(avatar_taken_down_letter(submission), [submission.user])
