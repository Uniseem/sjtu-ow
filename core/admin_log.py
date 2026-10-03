"""Wagtail's action log for the admin's own buttons (design 14.4, round 119).

Wagtail logs what its generic views do (create, edit, delete); publishing a
tournament, disbanding a team or saving a scrim split happen in this site's
own views, so they write here. The entries show on the object's history
page and in 「报告 → 网站历史」.
"""

from __future__ import annotations

import logging

from wagtail.log_actions import log as wagtail_log

logger = logging.getLogger(__name__)

# action -> (label in the history filter, sentence in the history list)
ACTIONS = {
    "tournaments.publish": ("发布赛事", "发布了赛事"),
    "tournaments.finish": ("标记赛事结束", "把赛事标记为已结束"),
    "tournaments.cancel": ("取消赛事", "取消了赛事"),
    "tournaments.arrange": ("保存队伍编排", "保存了队伍编排"),
    "scrims.publish": ("发布内战", "发布了内战"),
    "scrims.finish": ("标记内战结束", "把内战标记为已结束"),
    "scrims.cancel": ("取消内战", "取消了内战"),
    "scrims.select": ("保存上场名单", "保存了上场名单"),
    "scrims.generate": ("生成分队", "生成了分队"),
    "scrims.save_teams": ("保存分队", "保存了分队"),
    "teams.assign_captain": ("指定队长", "指定了队长"),
    "teams.disband": ("解散战队", "解散了战队"),
}


def record(instance, action: str, user, **data) -> None:
    """Write one entry; a failure here must never undo the action itself."""
    try:
        wagtail_log(instance=instance, action=action, user=user, data=data)
    except Exception:  # noqa: BLE001
        logger.warning("操作记录写入失败 %s", action, exc_info=True)
