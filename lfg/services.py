"""LFG business rules (design 6)."""

from __future__ import annotations

import logging
from datetime import timedelta

from django.db.models import Case, IntegerField, Q, When
from django.utils import timezone

from lfg.models import LfgPost, LfgStatus

logger = logging.getLogger(__name__)

EARLIEST_MINUTES = 10  # 开车时间最早是当前时间前 10 分钟（设计 6.1）
LATEST_DAYS = 7


class LfgError(Exception):
    """Something the user may not do right now; the message is shown."""


def site_settings():
    from core.models import SiteSettings

    return SiteSettings.load()


def max_active_posts() -> int:
    return int(site_settings().lfg_max_active_posts or 3)


def expire_hours() -> int:
    return int(site_settings().lfg_expire_hours or 2)


def expires_for(start_at):
    return start_at + timedelta(hours=expire_hours())


def active_posts():
    """Posts a visitor should see (design 6.3)."""
    now = timezone.now()
    return (
        LfgPost.objects.filter(
            status__in=[LfgStatus.OPEN, LfgStatus.FULL],
            expires_at__gt=now,
            owner__is_active=True,
        )
        .select_related("owner", "mode", "game_account")
        .annotate(
            full_last=Case(
                When(status=LfgStatus.FULL, then=1),
                default=0,
                output_field=IntegerField(),
            )
        )
        .order_by("full_last", "start_at")
    )


def my_active_count(user) -> int:
    return LfgPost.objects.filter(
        owner=user,
        status__in=[LfgStatus.OPEN, LfgStatus.FULL],
        expires_at__gt=timezone.now(),
    ).count()


def open_count() -> int:
    return active_posts().filter(status=LfgStatus.OPEN).count()


def can_post(user) -> tuple[bool, str]:
    from accounts.models import GameAccount
    from accounts.permissions import can_use, feature_denied_message

    if not getattr(user, "is_authenticated", False):
        return False, "请先登录。"
    if not can_use(user, "lfg_post"):
        return False, feature_denied_message("lfg_post")
    if not GameAccount.objects.filter(user=user).exists():
        return False, "请先在个人中心添加至少一个游戏 ID。"
    if my_active_count(user) >= max_active_posts():
        return False, f"你同时最多只能有 {max_active_posts()} 个未过期的车帖。"
    return True, ""


def check_start_at(start_at):
    now = timezone.now()
    if start_at < now - timedelta(minutes=EARLIEST_MINUTES):
        raise LfgError("开车时间不能早于当前时间 10 分钟前。")
    if start_at > now + timedelta(days=LATEST_DAYS):
        raise LfgError("开车时间最多只能排到 7 天后。")


def create_post(*, user, game_account, mode, roles, start_at, note="") -> LfgPost:
    allowed, reason = can_post(user)
    if not allowed:
        raise LfgError(reason)
    if game_account.user_id != user.pk:
        raise LfgError("只能使用自己的游戏 ID。")
    if not mode.is_active:
        raise LfgError("这个模式已经停用了。")
    if not any(roles.values()):
        raise LfgError("请至少选择一个缺的位置。")
    check_start_at(start_at)

    post = LfgPost.objects.create(
        owner=user,
        game_account=game_account,
        mode=mode,
        role_tank=bool(roles.get("tank")),
        role_damage=bool(roles.get("damage")),
        role_support=bool(roles.get("support")),
        start_at=start_at,
        expires_at=expires_for(start_at),
        note=note,
    )
    after_change(post)
    return post


def update_post(*, post, user, game_account, mode, roles, start_at, note="") -> LfgPost:
    if post.owner_id != user.pk:
        raise LfgError("只能修改自己的车帖。")
    if post.status == LfgStatus.CLOSED:
        raise LfgError("已关闭的车帖不能再修改。")
    if game_account.user_id != user.pk:
        raise LfgError("只能使用自己的游戏 ID。")
    if not any(roles.values()):
        raise LfgError("请至少选择一个缺的位置。")
    check_start_at(start_at)

    post.game_account = game_account
    post.mode = mode
    post.role_tank = bool(roles.get("tank"))
    post.role_damage = bool(roles.get("damage"))
    post.role_support = bool(roles.get("support"))
    post.start_at = start_at
    post.expires_at = expires_for(start_at)  # 改时间就重算过期
    post.note = note
    post.save()
    after_change(post)
    return post


def set_status(*, post, user, status) -> LfgPost:
    from moderation.admin_views import can_review

    is_admin = can_review(user)
    if post.owner_id != user.pk and not is_admin:
        raise LfgError("只能修改自己的车帖。")
    if post.status == LfgStatus.CLOSED:
        raise LfgError("已关闭的车帖不能重新打开。")
    if status not in LfgStatus.values:
        raise LfgError("未知的状态。")
    post.status = status
    post.save(update_fields=["status", "updated_at"])
    after_change(post)
    return post


def after_change(post) -> None:
    """The note goes through AI review; the board itself is loaded live."""
    if not post.note:
        return
    from moderation import services as moderation_services

    try:
        moderation_services.submit(
            target_type="lfg_note",
            target_id=post.pk,
            field="note",
            text=post.note,
            url="/lfg/",
            author=post.owner,
        )
    except Exception:  # noqa: BLE001 — review must never block posting
        logger.warning("车帖备注送审失败 #%s", post.pk, exc_info=True)


def filtered_posts(*, mode_id=None, roles=(), open_only=False):
    posts = active_posts()
    if mode_id:
        posts = posts.filter(mode_id=mode_id)
    role_filter = Q()
    if "tank" in roles:
        role_filter |= Q(role_tank=True)
    if "damage" in roles:
        role_filter |= Q(role_damage=True)
    if "support" in roles:
        role_filter |= Q(role_support=True)
    if role_filter:
        posts = posts.filter(role_filter)
    if open_only:
        posts = posts.filter(status=LfgStatus.OPEN)
    return posts
