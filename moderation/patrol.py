"""The AI's rounds (design 5.5.3, 5.5.4, v6.72, round 194).

Saving content only puts it on record (``services.submit``). Every
``PATROL_MINUTES`` the worker sends what has not been read yet: short texts
twenty to a request, long ones whole in chunks. Then one letter lists what
the AI found doubtful, to the address set in 全站设置 or the superusers.
Nothing on the site is hidden or held back: everyone is trusted by default.
"""

from __future__ import annotations

import logging

from django.core.cache import cache
from django.utils import timezone

from moderation import services
from moderation.models import ModerationItem, Risk

logger = logging.getLogger(__name__)

PATROL_MINUTES = 30
PATROL_KEY = "moderation-patrol"
# What the letter counts as doubtful; 「无法判定」 is not a finding.
DOUBTFUL = (Risk.LOW, Risk.MEDIUM, Risk.HIGH)


def review_short_batch(items) -> int:
    """One request for up to twenty short texts. Returns how many were
    settled, 0 when today's quota is used up."""
    from moderation.providers import get_provider

    remaining = [item for item in items if not services.copy_recent_verdict(item)]
    if not remaining:
        return len(items)
    if services.quota_left() <= 0:
        return 0
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
        services.record(
            item,
            risk=verdict.risk if verdict else Risk.UNKNOWN,
            categories=verdict.categories if verdict else [],
            reason=verdict.reason if verdict else "模型漏掉了这一条",
            quote=verdict.quote if verdict else "",
            model=result.model or model,
            input_tokens=share_in,
            output_tokens=share_out,
        )
    return len(items)


def review_long(item) -> bool:
    """One longer piece in full, chunked (5.5.3: 不截断内容). False when
    today's quota is used up."""
    from moderation.providers import get_provider

    if services.copy_recent_verdict(item):
        return True
    if services.quota_left() <= 0:
        return False
    chunks = services.split_text(item.full_text or item.excerpt)
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
    return True


def review_pending() -> int:
    """Everything not read yet, until it is done or today's quota is."""
    if not services.is_enabled():
        return 0
    reviewed = 0
    while True:
        items = services.pending_short_items()
        if not items:
            break
        done = review_short_batch(items)
        if not done:
            return reviewed
        reviewed += done
    for item in services.pending_long_items(limit=None):
        if not review_long(item):
            break
        reviewed += 1
    return reviewed


def run() -> tuple[int, int]:
    """One round: (pieces read, pieces in the letter)."""
    from moderation.notifications import send_patrol_alert

    reviewed = review_pending()
    return reviewed, send_patrol_alert()


def enqueue_if_due() -> bool:
    """Called on the worker's beat: at most one round per PATROL_MINUTES
    (the shared cache key lives that long)."""
    from moderation.tasks import patrol

    if not cache.add(PATROL_KEY, timezone.now().isoformat(), PATROL_MINUTES * 60):
        return False
    patrol.enqueue()
    return True


def doubtful_unsent():
    return ModerationItem.objects.filter(
        risk__in=DOUBTFUL, checked_at__isnull=False, notified_at__isnull=True
    ).order_by("checked_at")
