"""Emails about uploaded faces (design 10.2, design-details 2.3; v6.11),
written as letters (10.3).

``*_letter`` builds what one email says; the function next to it sends it
(see teams.notifications). The specimen page /_styleguide/emails/ renders
the builders with sample data.
"""

from __future__ import annotations

from django.conf import settings
from django.urls import reverse
from django.utils.timezone import localtime

from core.letters import Letter, send, site_url

# New uploads wait this long, so one email lists everything that came in.
WAITING_DELAY_SECONDS = 10 * 60
WAITING_KEY = "avatars:waiting-pending"
REVIEWER_WHY = "你收到这封邮件，是因为你是内容编辑或超级管理员，负责审核头像。"


def _profile_url() -> str:
    return site_url(reverse("me_profile"))


def _why_owner() -> str:
    return "你收到这封邮件，是因为你在社区上传过头像。"


def _review_facts(submission) -> list[tuple[str, str]]:
    facts = [("原因", submission.get_reason_display() or "（未填写）")]
    if submission.note:
        facts.append(("说明", submission.note))
    return facts


def avatar_rejected_letter(submission) -> Letter:
    return Letter(
        subject="头像没有通过审核",
        lead="你上传的头像没有通过审核，没有换上，大家看到的还是原来的头像。",
        facts=_review_facts(submission),
        paragraphs=["那张图已经删除。你可以换一张重新上传。"],
        action=("重新上传", _profile_url()),
        reason=_why_owner(),
    )


def avatar_rejected(submission) -> None:
    send(avatar_rejected_letter(submission), [submission.user])


def avatar_taken_down_letter(submission) -> Letter:
    return Letter(
        subject="你的头像已被撤下",
        lead="你正在用的头像被管理员撤下了，现在显示的是默认头像。",
        facts=_review_facts(submission),
        paragraphs=["那张图已经删除。你可以换一张重新上传，审核通过后会换上。"],
        action=("重新上传", _profile_url()),
        reason=_why_owner(),
    )


def avatar_taken_down(submission) -> None:
    send(avatar_taken_down_letter(submission), [submission.user])


def review_url() -> str:
    base = getattr(settings, "WAGTAILADMIN_BASE_URL", "") or ""
    return base.rstrip("/") + reverse("avatar_review")


def _uploaded(submission) -> str:
    when = localtime(submission.created_at)
    return f"{submission.user.nickname}，{when:%Y.%m.%d %H:%M} 上传"


def avatars_waiting_letter(pending) -> Letter:
    return Letter(
        subject=f"有 {len(pending)} 张头像等审核",
        lead=(
            f"成员上传了新头像，现在有 {len(pending)} 张在等审核。"
            "审核通过之前，大家看到的还是他们原来的头像。"
        ),
        items=[(_uploaded(item), "") for item in pending],
        action=("去后台审核", review_url()),
        reason=REVIEWER_WHY,
    )


def avatars_waiting_soon() -> bool:
    """Ask for one reminder in WAITING_DELAY_SECONDS: uploads in between are
    listed in the same email (10.2)."""
    from datetime import timedelta

    from django.core.cache import cache
    from django.db import transaction
    from django.utils import timezone

    from accounts.tasks import notify_avatars_waiting

    # Held until the reminder goes out (the task clears it); twice the delay
    # so a stopped worker does not silence reminders for good.
    if not cache.add(WAITING_KEY, 1, WAITING_DELAY_SECONDS * 2):
        return False  # a reminder is already on its way
    run_after = timezone.now() + timedelta(seconds=WAITING_DELAY_SECONDS)
    transaction.on_commit(
        lambda: notify_avatars_waiting.using(run_after=run_after).enqueue()
    )
    return True


def send_avatars_waiting() -> int:
    """One email to the reviewers listing every face still waiting."""
    from accounts.models import AvatarSubmission
    from moderation.notifications import reviewer_emails

    pending = list(
        AvatarSubmission.objects.filter(status=AvatarSubmission.Status.PENDING)
        .select_related("user")
        .order_by("created_at")
    )
    if not pending:
        return 0
    recipients = reviewer_emails()
    if not recipients:
        return 0
    send(avatars_waiting_letter(pending), recipients)
    return len(pending)
