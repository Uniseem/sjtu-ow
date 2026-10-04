"""Worker tasks for AI moderation (design 5.5.3, v6.72).

One task: the patrol. The worker's beat enqueues it every
``patrol.PATROL_MINUTES`` (``patrol.enqueue_if_due``). Until v6.72 every save
queued its own review, a digest went out each morning and a button queued a
night-time full scan.
"""

from __future__ import annotations

import logging

from django_tasks import task

logger = logging.getLogger(__name__)


@task
def patrol() -> None:
    from moderation import patrol as rounds

    reviewed, alerted = rounds.run()
    if reviewed or alerted:
        logger.info("AI 巡查：看了 %s 条，提醒 %s 条", reviewed, alerted)
