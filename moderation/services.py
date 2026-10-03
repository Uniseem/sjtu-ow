"""Submitting content for AI review and recording the verdicts (design 5.5).

Nothing in this module changes content, accounts or visibility. The only thing
the AI path ever writes is a ModerationItem row; a reviewer's actions at the
end record how an item was handled and may write to its author.
"""

from __future__ import annotations

import hashlib
import logging
import re
from datetime import timedelta

from django.db import transaction
from django.utils import timezone

from moderation.models import ModerationItem, ModerationUsage, Risk, TargetType

logger = logging.getLogger(__name__)

MAX_BATCH = 20  # short items per request (design 5.5.3)
DEDUPE_DAYS = 30
CHUNK_CHARS = 8000
EXCERPT_CHARS = 2000
SHORT_TYPES = {
    TargetType.NICKNAME,
    TargetType.MOTTO,
    TargetType.TEAM_NAME,
    TargetType.COMMENT,
}
BATCH_DELAY_SECONDS = 10
# Peak price, USD per million tokens (design 5.5.3).
INPUT_PRICE = 0.3
OUTPUT_PRICE = 1.2


def site_settings():
    from core.models import SiteSettings

    return SiteSettings.load()


def is_configured() -> bool:
    """A key (or a self-hosted base URL) has to be set before we call anything."""
    from django.conf import settings

    return bool(
        getattr(settings, "MODERATION_API_KEY", "")
        or getattr(settings, "MODERATION_BASE_URL", "")
    )


def is_enabled() -> bool:
    """On in the admin **and** configured; otherwise nothing is submitted.

    Without this second half a fresh install would fill the queue with
    「无法判定」 rows from calls that were never going to succeed.
    """
    if not is_configured():
        return False
    try:
        return bool(site_settings().moderation_enabled)
    except Exception:  # noqa: BLE001 — settings row may not exist yet
        return False


def current_model() -> str:
    try:
        return site_settings().moderation_model or "deepseek-v4.1-flash"
    except Exception:  # noqa: BLE001
        return "deepseek-v4.1-flash"


def daily_limit() -> int:
    try:
        return int(site_settings().moderation_daily_limit or 0)
    except Exception:  # noqa: BLE001
        return 0


def text_hash(text: str) -> str:
    return hashlib.sha256(text.strip().encode("utf-8")).hexdigest()


def submit(
    *,
    target_type: str,
    target_id: int,
    field: str,
    text: str,
    url: str = "",
    author=None,
) -> ModerationItem | None:
    """Queue one piece of content. Returns the record, or None if skipped."""
    from moderation.tasks import review_item, review_short_items

    text = (text or "").strip()
    if not text or not is_enabled():
        return None

    digest = text_hash(text)
    item, created = ModerationItem.objects.get_or_create(
        target_type=target_type,
        target_id=target_id or 0,
        field=field,
        text_hash=digest,
        defaults={
            "excerpt": text[:EXCERPT_CHARS],
            "url": url,
            "author": author if getattr(author, "pk", None) else None,
            "risk": Risk.UNKNOWN,
            "model": "",
        },
    )
    if not created:
        return item  # same text on the same target: already on record

    if target_type in SHORT_TYPES:
        run_after = timezone.now() + timedelta(seconds=BATCH_DELAY_SECONDS)
        transaction.on_commit(
            lambda: review_short_items.using(run_after=run_after).enqueue()
        )
    else:
        # The row only keeps an excerpt; the task carries the whole text so a
        # long article is reviewed in full (design 5.5.3: 不截断内容).
        transaction.on_commit(lambda: review_item.enqueue(item.pk, text))
    return item


def used_today() -> ModerationUsage:
    usage, _ = ModerationUsage.objects.get_or_create(date=timezone.localdate())
    return usage


def quota_left() -> int:
    limit = daily_limit()
    if limit <= 0:
        return 0
    return max(0, limit - used_today().calls)


def note_usage(*, calls: int, items: int, input_tokens: int, output_tokens: int):
    usage = used_today()
    ModerationUsage.objects.filter(pk=usage.pk).update(
        calls=usage.calls + calls,
        items=usage.items + items,
        input_tokens=usage.input_tokens + input_tokens,
        output_tokens=usage.output_tokens + output_tokens,
    )


def estimated_cost(input_tokens: int, output_tokens: int) -> float:
    return (
        input_tokens / 1_000_000 * INPUT_PRICE
        + output_tokens / 1_000_000 * OUTPUT_PRICE
    )


def recent_verdict(digest: str, exclude_pk=None):
    """A verdict for the same text within the dedupe window (design 5.5.3)."""
    cutoff = timezone.now() - timedelta(days=DEDUPE_DAYS)
    query = ModerationItem.objects.filter(
        text_hash=digest,
        checked_at__gte=cutoff,
    ).exclude(pk=exclude_pk)
    return query.order_by("-checked_at").first()


def record(
    item: ModerationItem,
    *,
    risk,
    categories,
    reason,
    quote,
    model,
    input_tokens: int = 0,
    output_tokens: int = 0,
) -> None:
    """Write the AI's answer. This is the AI path's only write (design 5.5)."""
    item.risk = risk if risk in Risk.values else Risk.UNKNOWN
    item.categories = list(categories or [])
    item.reason = reason or ""
    item.quote = quote or ""
    item.model = model or ""
    item.input_tokens = int(input_tokens or 0)
    item.output_tokens = int(output_tokens or 0)
    item.checked_at = timezone.now()
    if item.risk == Risk.NONE:
        # Nothing for a human to look at; keep the row for statistics only.
        item.status = ModerationItem.Status.OK
    item.save(
        update_fields=[
            "risk",
            "categories",
            "reason",
            "quote",
            "model",
            "input_tokens",
            "output_tokens",
            "checked_at",
            "status",
        ]
    )
    if item.risk == Risk.HIGH:
        from moderation.notifications import notify_high_risk

        notify_high_risk(item)


def copy_recent_verdict(item: ModerationItem) -> bool:
    """Reuse an identical text's verdict instead of paying for it again."""
    previous = recent_verdict(item.text_hash, exclude_pk=item.pk)
    if previous is None:
        return False
    record(
        item,
        risk=previous.risk,
        categories=previous.categories,
        reason=previous.reason or "与 30 天内已审核过的相同内容一致",
        quote=previous.quote,
        model=previous.model,
    )
    return True


def split_text(text: str) -> list[str]:
    """Long content goes in whole, in paragraph-sized chunks (design 5.5.3)."""
    if len(text) <= CHUNK_CHARS:
        return [text]
    chunks: list[str] = []
    current = ""
    for paragraph in re.split(r"\n{2,}", text):
        if current and len(current) + len(paragraph) + 2 > CHUNK_CHARS:
            chunks.append(current)
            current = paragraph
        elif len(paragraph) > CHUNK_CHARS:
            if current:
                chunks.append(current)
                current = ""
            for start in range(0, len(paragraph), CHUNK_CHARS):
                chunks.append(paragraph[start : start + CHUNK_CHARS])
        else:
            current = f"{current}\n\n{paragraph}" if current else paragraph
    if current:
        chunks.append(current)
    return chunks


RISK_ORDER = {
    Risk.NONE: 0,
    Risk.LOW: 1,
    Risk.MEDIUM: 2,
    Risk.HIGH: 3,
    Risk.UNKNOWN: 1,  # worth a look, but below a real medium
}


def worst(verdicts):
    """The highest risk among chunk verdicts (design 5.5.3)."""
    return max(verdicts, key=lambda verdict: RISK_ORDER.get(verdict.risk, 0))


def pending_short_items(limit: int = MAX_BATCH):
    return list(
        ModerationItem.objects.filter(
            checked_at__isnull=True,
            target_type__in=list(SHORT_TYPES),
        ).order_by("created_at")[:limit]
    )


def pending_long_items(limit: int = 50):
    return list(
        ModerationItem.objects.filter(checked_at__isnull=True)
        .exclude(target_type__in=list(SHORT_TYPES))
        .order_by("created_at")[:limit]
    )


MODERATION_PERMISSIONS = ("view_moderationitem", "change_moderationitem")
REVIEWER_GROUPS = ("内容编辑",)


def assign_moderation_permissions() -> list[str]:
    """Content editors may read and act on the review queue (design 5.5.4)."""
    from django.contrib.auth.models import Group, Permission

    granted = []
    permissions = list(
        Permission.objects.filter(
            content_type__app_label="moderation",
            codename__in=MODERATION_PERMISSIONS,
        )
    )
    for name in REVIEWER_GROUPS:
        group = Group.objects.filter(name=name).first()
        if group is None:
            continue
        group.permissions.add(*permissions)
        granted.append(group.name)
    return granted


def month_usage():
    """Exact call and token totals for the current month (design 5.5.3)."""
    today = timezone.localdate()
    rows = ModerationUsage.objects.filter(
        date__year=today.year,
        date__month=today.month,
    )
    totals = {"calls": 0, "items": 0, "input_tokens": 0, "output_tokens": 0}
    for row in rows:
        totals["calls"] += row.calls
        totals["items"] += row.items
        totals["input_tokens"] += row.input_tokens
        totals["output_tokens"] += row.output_tokens
    totals["cost"] = estimated_cost(totals["input_tokens"], totals["output_tokens"])
    return totals


# --- what a reviewer does (design 5.5.4) ------------------------------------

REVISE_LOG_ACTION = "moderation.ask_author"
REVISE_MAX_CHARS = 500


class ModerationError(Exception):
    pass


def author_problem(item) -> str:
    """Why this item's author cannot be written to; "" when they can."""
    author = item.author
    if author is None:
        return "这条内容没有作者（系统内容，或作者已注销），不能发信。"
    if not author.is_active:
        return "作者的账号已停用，不能发信。"
    if not author.email:
        return "作者没有邮箱，不能发信。"
    return ""


@transaction.atomic
def ask_author_to_revise(*, item, actor, message: str) -> ModerationItem:
    """Email the author what to change (v6.17: the one direct action the
    review page takes, 「直接处置只做发信」). The item counts as handled;
    the whole message stays in the action log."""
    from wagtail.log_actions import log as wagtail_log

    from moderation.notifications import ask_author

    message = (message or "").strip()
    if not message:
        raise ModerationError("写一段说明，告诉作者要改什么。")
    if len(message) > REVISE_MAX_CHARS:
        raise ModerationError(f"说明最多 {REVISE_MAX_CHARS} 字。")
    problem = author_problem(item)
    if problem:
        raise ModerationError(problem)
    item.status = ModerationItem.Status.HANDLED
    item.handling_note = "已发信要求作者修改"
    item.reviewed_by = actor
    item.reviewed_at = timezone.now()
    item.save(update_fields=["status", "handling_note", "reviewed_by", "reviewed_at"])
    wagtail_log(
        instance=item,
        action=REVISE_LOG_ACTION,
        user=actor,
        data={"result": "要求作者修改（已发信）", "note": message},
    )
    transaction.on_commit(lambda: ask_author(item, message))
    return item


# --- checking the connection (round 122) ------------------------------------

TRY_SAMPLE = "这是后台「试一下」发出的测试内容：周五晚上八点内战，欢迎大家来玩。"


def disabled_reason() -> str:
    """Why nothing is being reviewed, in words the owner can act on."""
    if not is_configured():
        return (
            "服务器没有设置环境变量 MODERATION_API_KEY（或自建服务的 "
            "MODERATION_BASE_URL），AI 审核不会运行。写进 .env 后重启 web 和 worker。"
        )
    if not is_enabled():
        return "全站设置里「启用 AI 内容审核」关着，新内容不会送审。"
    return ""


def try_connection():
    """Send one harmless sample and return (ok, message). Works while the
    switch is still off, so the owner can check the key before turning it
    on; it counts towards today's usage like any call."""
    from moderation.providers import get_provider

    if not is_configured():
        return False, disabled_reason()
    model = current_model()
    result = get_provider().review([TRY_SAMPLE], model=model)
    note_usage(
        calls=1,
        items=1,
        input_tokens=result.input_tokens,
        output_tokens=result.output_tokens,
    )
    verdict = result.verdicts[0] if result.verdicts else None
    if verdict is None or verdict.risk == Risk.UNKNOWN:
        reason = verdict.reason if verdict else "没有返回结果"
        hint = ""
        if "401" in reason or "403" in reason:
            hint = "（多半是密钥不对）"
        elif "404" in reason:
            hint = "（多半是模型名或服务地址不对）"
        return False, f"连不上 AI 审核：{reason}{hint}。模型 {model}。"
    used = result.input_tokens + result.output_tokens
    label = dict(Risk.choices).get(verdict.risk, verdict.risk)
    return True, (
        f"AI 审核能用：模型 {result.model or model} 把测试内容判为"
        f"「{label}」，用了 {used} 个 token。"
    )
