"""Worker tasks for webhook delivery (design 11.8.3)."""

from __future__ import annotations

import logging

from django.utils import timezone
from django_tasks import task

from integrations import webhooks
from integrations.models import DeliveryStatus, WebhookDelivery

logger = logging.getLogger(__name__)


@task
def deliver_webhook(delivery_id: int) -> str:
    """One attempt. Reschedules itself until it succeeds or runs out of tries."""
    delivery = (
        WebhookDelivery.objects.select_related("client").filter(pk=delivery_id).first()
    )
    if delivery is None:
        return "gone"
    if delivery.status != DeliveryStatus.PENDING:
        return "done"
    if not delivery.client.usable or not delivery.client.webhook_url:
        return "skipped"

    due = delivery.next_attempt_at
    if due is not None and due > timezone.now():
        # Woken early; come back when it is actually due.
        deliver_webhook.using(run_after=due).enqueue(delivery_id)
        return "deferred"

    if webhooks.attempt(delivery):
        return "succeeded"
    if delivery.status == DeliveryStatus.FAILED:
        logger.warning(
            "Webhook %s 投递失败，已用完 %s 次机会",
            delivery.event_id,
            delivery.attempts,
        )
        return "failed"
    deliver_webhook.using(run_after=delivery.next_attempt_at).enqueue(delivery_id)
    return "retrying"


@task
def deliver_due_webhooks() -> int:
    """Safety net: pick up anything the queue lost (design 11.8.3)."""
    due = WebhookDelivery.objects.filter(
        status=DeliveryStatus.PENDING, next_attempt_at__lte=timezone.now()
    ).values_list("pk", flat=True)[:200]
    count = 0
    for pk in list(due):
        deliver_webhook.enqueue(pk)
        count += 1
    return count
