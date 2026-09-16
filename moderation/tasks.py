"""Worker tasks for AI moderation (design 5.5.3)."""

from __future__ import annotations

import logging
from datetime import datetime, time, timedelta

from django.utils import timezone
from django_tasks import task

from moderation import services
from moderation.models import ModerationItem, Risk

logger = logging.getLogger(__name__)

NEXT_DAY_HOUR = 0
NEXT_DAY_MINUTE = 5


def _tomorrow_run_after():
    """Over the daily cap: try again just after midnight (design 5.5.3)."""
    tomorrow = timezone.localdate() + timedelta(days=1)
    naive = datetime.combine(tomorrow, time(NEXT_DAY_HOUR, NEXT_DAY_MINUTE))
    return timezone.make_aware(naive)


@task
def review_item(item_id: int, full_text: str = "") -> None:
    """Review one longer piece of content in full, chunking it if needed."""
    from moderation.providers import get_provider

    item = ModerationItem.objects.filter(pk=item_id, checked_at__isnull=True).first()
    if item is None or not services.is_enabled():
        return
    if services.copy_recent_verdict(item):
        return
    if services.quota_left() <= 0:
        review_item.using(run_after=_tomorrow_run_after()).enqueue(item_id, full_text)
        return

    chunks = services.split_text(full_text or item.excerpt)
    provider = get_provider()
    model = services.current_model()
    result = provider.review(chunks, model=model)
    services.note_usage(
        calls=1,
        items=len(chunks),
        input_tokens=result.input_tokens,
        output_tokens=result.output_tokens,
    )
    verdict = services.worst(result.verdicts)
    services.record(
        item,
        risk=verdict.risk,
        categories=verdict.categories,
        reason=verdict.reason,
        quote=verdict.quote,
        model=result.model or model,
        input_tokens=result.input_tokens,
        output_tokens=result.output_tokens,
    )


@task
def review_short_items() -> None:
    """Review queued short texts in one request (design 5.5.3)."""
    from moderation.providers import get_provider

    if not services.is_enabled():
        return
    items = services.pending_short_items()
    if not items:
        return

    remaining = []
    for item in items:
        if not services.copy_recent_verdict(item):
            remaining.append(item)
    if not remaining:
        return
    if services.quota_left() <= 0:
        review_short_items.using(run_after=_tomorrow_run_after()).enqueue()
        return

    provider = get_provider()
    model = services.current_model()
    result = provider.review([item.excerpt for item in remaining], model=model)
    services.note_usage(
        calls=1,
        items=len(remaining),
        input_tokens=result.input_tokens,
        output_tokens=result.output_tokens,
    )
    by_index = {verdict.index: verdict for verdict in result.verdicts}
    share_in = result.input_tokens // max(len(remaining), 1)
    share_out = result.output_tokens // max(len(remaining), 1)
    for index, item in enumerate(remaining):
        verdict = by_index.get(index)
        if verdict is None:
            services.record(
                item,
                risk=Risk.UNKNOWN,
                categories=[],
                reason="模型漏掉了这一条",
                quote="",
                model=result.model or model,
                input_tokens=share_in,
                output_tokens=share_out,
            )
            continue
        services.record(
            item,
            risk=verdict.risk,
            categories=verdict.categories,
            reason=verdict.reason,
            quote=verdict.quote,
            model=result.model or model,
            input_tokens=share_in,
            output_tokens=share_out,
        )

    if services.pending_short_items():
        review_short_items.enqueue()


@task
def send_moderation_digest() -> None:
    """Daily summary of medium/low findings (design 5.5.4)."""
    from moderation.notifications import send_digest

    send_digest()
