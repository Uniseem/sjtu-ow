"""The AI's rounds (design 5.5.3, 5.5.4, v6.72, round 194; v7.2, round 198).

Saving content only puts it on record (``services.submit``). Every
``PATROL_MINUTES`` the worker sends what has not been read yet: short texts
in batches sized to the output limit, long ones whole, one chunk per
request. Then one letter lists what the AI found doubtful, to the address set
in 全站设置 or the superusers. Nothing on the site is hidden or held back:
everyone is trusted by default.

v7.2: a review that did not come back leaves its items waiting
(``services.note_failure``) and ends the round; one patrol task holds the
single worker for at most ``PATROL_SECONDS`` and leaves the rest to a
follow-up queued behind whatever else is waiting.
"""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass
from datetime import timedelta

from django.core.cache import cache
from django.utils import timezone

from moderation import services
from moderation.models import ModerationItem, Risk

logger = logging.getLogger(__name__)

PATROL_MINUTES = 30
PATROL_KEY = "moderation-patrol"
# How long one patrol task may hold the worker: mail and prerendering wait
# behind it. No new request starts after this; the rest goes to a follow-up.
PATROL_SECONDS = 60
# Below the default 0, so whatever is already waiting runs first.
FOLLOW_UP_PRIORITY = -10
# What the letter counts as doubtful; 「无法判定」 is not a finding.
DOUBTFUL = (Risk.LOW, Risk.MEDIUM, Risk.HIGH)

# Why a round ended before everything was read.
QUOTA = "quota"
FAILED = "failed"
TIME = "time"


@dataclass
class Round:
    reviewed: int = 0
    stopped: str = ""  # QUOTA, FAILED or TIME; "" when nothing is left


def review_short_batch(items, tally: Round) -> str:
    """One request for a batch of short texts. Returns why the round has to
    stop, "" to go on."""
    from moderation.providers import get_provider

    remaining = [item for item in items if not services.copy_recent_verdict(item)]
    tally.reviewed += len(items) - len(remaining)
    if not remaining:
        return ""
    if services.quota_left() <= 0:
        return QUOTA
    model = services.current_model()
    result = get_provider().review([item.excerpt for item in remaining], model=model)
    services.note_usage(
        calls=1,
        items=len(remaining),
        input_tokens=result.input_tokens,
        output_tokens=result.output_tokens,
    )
    if result.error:
        services.note_failure(remaining, result.error, counts=result.counts)
        return FAILED
    by_index = {verdict.index: verdict for verdict in result.verdicts}
    share_in = result.input_tokens // len(remaining)
    share_out = result.output_tokens // len(remaining)
    for index, item in enumerate(remaining):
        verdict = by_index.get(index)
        if verdict is None or verdict.error:
            # Left out of an otherwise good answer: alone next time.
            missed = verdict.error if verdict else "模型漏掉了这一条"
            services.note_failure([item], missed, counts=True)
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
        tally.reviewed += 1
    return ""


def review_long(item, tally: Round) -> str:
    """One longer piece in full (5.5.3: 不截断内容), a request per chunk so
    no answer outgrows the output limit; a high risk ends it early."""
    from moderation.providers import get_provider

    if services.copy_recent_verdict(item):
        tally.reviewed += 1
        return ""
    if services.quota_left() <= 0:
        return QUOTA
    provider = get_provider()
    model = services.current_model()
    verdicts = []
    used_model = model
    input_tokens = output_tokens = 0
    for chunk in services.split_text(item.full_text or item.excerpt):
        if services.quota_left() <= 0:
            return QUOTA
        result = provider.review([chunk], model=model)
        services.note_usage(
            calls=1,
            items=1,
            input_tokens=result.input_tokens,
            output_tokens=result.output_tokens,
        )
        input_tokens += result.input_tokens
        output_tokens += result.output_tokens
        if result.error:
            services.note_failure([item], result.error, counts=result.counts)
            return FAILED
        verdicts.append(result.verdicts[0])
        used_model = result.model or model
        if verdicts[-1].risk == Risk.HIGH:
            break  # nothing in the rest can be worse
    verdict = services.worst(verdicts)
    services.record(
        item,
        risk=verdict.risk,
        categories=verdict.categories,
        reason=verdict.reason,
        quote=verdict.quote,
        model=used_model,
        input_tokens=input_tokens,
        output_tokens=output_tokens,
    )
    tally.reviewed += 1
    return ""


def review_pending(seconds: float | None = None) -> Round:
    """What has not been read yet, until it is done, today's quota is, a call
    fails, or this task's share of the worker is used up."""
    tally = Round()
    if not services.is_enabled():
        return tally
    deadline = time.monotonic() + (PATROL_SECONDS if seconds is None else seconds)
    while items := services.pending_short_items():
        if time.monotonic() >= deadline:
            tally.stopped = TIME
            return tally
        tally.stopped = review_short_batch(items, tally)
        if tally.stopped:
            return tally
    while items := services.pending_long_items(limit=1):
        if time.monotonic() >= deadline:
            tally.stopped = TIME
            return tally
        tally.stopped = review_long(items[0], tally)
        if tally.stopped:
            return tally
    return tally


def run() -> tuple[int, int]:
    """One go: (pieces read, pieces in the letter). When time ran out the
    rest is queued, and the letter waits for the end of the round unless the
    oldest finding has waited a full patrol interval already."""
    from moderation.notifications import send_patrol_alert

    tally = review_pending()
    if tally.stopped == TIME:
        follow_up()
        if not letter_overdue():
            return tally.reviewed, 0
    return tally.reviewed, send_patrol_alert()


def follow_up() -> None:
    """Queue the rest behind whatever is waiting, and keep the beat from
    queueing another round meanwhile (design 5.5.3, v7.2)."""
    from moderation.tasks import patrol

    cache.set(PATROL_KEY, timezone.now().isoformat(), PATROL_MINUTES * 60)
    patrol.using(priority=FOLLOW_UP_PRIORITY).enqueue()


def letter_overdue() -> bool:
    oldest = doubtful_unsent().values_list("checked_at", flat=True).first()
    return oldest is not None and oldest <= timezone.now() - timedelta(
        minutes=PATROL_MINUTES
    )


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
