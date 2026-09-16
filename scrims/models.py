"""Scrims (design 9, 12.9)."""

from django.conf import settings
from django.db import models
from django.utils import timezone


class ScrimFormat(models.TextChoices):
    RQ_5V5 = "rq_5v5", "角色限定 5v5"
    RQ_6V6 = "rq_6v6", "角色限定 6v6"
    OPEN_5V5 = "open_5v5", "不限位置 5v5"
    OPEN_6V6 = "open_6v6", "不限位置 6v6"


class ScrimStatus(models.TextChoices):
    DRAFT = "draft", "草稿"
    PUBLISHED = "published", "已发布"
    FINISHED = "finished", "已结束"
    CANCELLED = "cancelled", "已取消"


class Team(models.TextChoices):
    A = "a", "A 队"
    B = "b", "B 队"


class Role(models.TextChoices):
    TANK = "tank", "坦克"
    DAMAGE = "damage", "输出"
    SUPPORT = "support", "支援"


ROLE_FIELDS = {
    Role.TANK: "role_tank",
    Role.DAMAGE: "role_damage",
    Role.SUPPORT: "role_support",
}
RANK_FIELDS = {
    Role.TANK: "rank_tank",
    Role.DAMAGE: "rank_damage",
    Role.SUPPORT: "rank_support",
}

# Design 9.4: per-team role requirements, and the team size each format needs.
ROLE_REQUIREMENTS = {
    ScrimFormat.RQ_5V5: {Role.TANK: 1, Role.DAMAGE: 2, Role.SUPPORT: 2},
    ScrimFormat.RQ_6V6: {Role.TANK: 2, Role.DAMAGE: 2, Role.SUPPORT: 2},
}
TEAM_SIZES = {
    ScrimFormat.RQ_5V5: 5,
    ScrimFormat.RQ_6V6: 6,
    ScrimFormat.OPEN_5V5: 5,
    ScrimFormat.OPEN_6V6: 6,
}
# A finished scrim stays on the public list for this long (design 9.2).
FINISHED_VISIBLE_DAYS = 30


class Scrim(models.Model):
    """One scrim night (design 9.1, 12.9.1)."""

    title = models.CharField("标题", max_length=100)
    description = models.TextField("说明", blank=True)
    starts_at = models.DateTimeField("开始时间")
    signup_closes_at = models.DateTimeField(
        "报名截止时间",
        null=True,
        blank=True,
        help_text="留空表示开始前都可以报名。",
    )
    format = models.CharField(
        "规格",
        max_length=16,
        choices=ScrimFormat.choices,
        default=ScrimFormat.RQ_5V5,
    )
    sjtu_only = models.BooleanField("仅限交大", default=False)
    status = models.CharField(
        "状态",
        max_length=16,
        choices=ScrimStatus.choices,
        default=ScrimStatus.DRAFT,
    )
    teams_generated_at = models.DateTimeField("分队时间", null=True, blank=True)
    # Design 9.2 wants the admin to see "分队有变化" after someone drops out.
    # A dedicated stamp, because ``updated_at`` also moves on ordinary edits.
    roster_changed_at = models.DateTimeField("名单变动时间", null=True, blank=True)
    reminder_sent_at = models.DateTimeField("提醒发送时间", null=True, blank=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        verbose_name="创建人",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="scrims_created",
    )
    created_at = models.DateTimeField("创建时间", auto_now_add=True)
    updated_at = models.DateTimeField("更新时间", auto_now=True)

    class Meta:
        verbose_name = "内战活动"
        verbose_name_plural = "内战活动"
        ordering = ["starts_at"]
        indexes = [
            models.Index(fields=["status", "starts_at"]),
        ]

    def __str__(self):
        return self.title

    @property
    def team_size(self) -> int:
        return TEAM_SIZES[self.format]

    @property
    def players_needed(self) -> int:
        return self.team_size * 2

    @property
    def role_queue(self) -> bool:
        return self.format in ROLE_REQUIREMENTS

    @property
    def signup_deadline(self):
        """Design 9.1: an empty deadline means "up until it starts"."""
        return self.signup_closes_at or self.starts_at

    def signup_open(self, now=None) -> bool:
        now = now or timezone.now()
        return self.status == ScrimStatus.PUBLISHED and now <= self.signup_deadline

    @property
    def is_public(self) -> bool:
        """Draft scrims do not exist as far as the front end is concerned."""
        return self.status != ScrimStatus.DRAFT


class ScrimSignup(models.Model):
    """One player's signup (design 9.2, 12.9.2)."""

    scrim = models.ForeignKey(
        Scrim,
        verbose_name="内战活动",
        on_delete=models.CASCADE,
        related_name="signups",
    )
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        verbose_name="玩家",
        on_delete=models.CASCADE,
        related_name="scrim_signups",
    )
    game_account = models.ForeignKey(
        "accounts.GameAccount",
        verbose_name="游戏 ID",
        on_delete=models.PROTECT,
        related_name="scrim_signups",
    )
    role_tank = models.BooleanField("坦克", default=False)
    role_damage = models.BooleanField("输出", default=False)
    role_support = models.BooleanField("支援", default=False)
    is_selected = models.BooleanField("上场", default=False)
    team = models.CharField(
        "队伍", max_length=1, choices=Team.choices, blank=True, default=""
    )
    assigned_role = models.CharField(
        "分到的位置", max_length=8, choices=Role.choices, blank=True, default=""
    )
    rating_used = models.PositiveSmallIntegerField(
        "分队使用的段位分数", null=True, blank=True
    )
    created_at = models.DateTimeField("报名时间", auto_now_add=True)
    updated_at = models.DateTimeField("更新时间", auto_now=True)

    class Meta:
        verbose_name = "内战报名"
        verbose_name_plural = "内战报名"
        ordering = ["created_at", "id"]
        constraints = [
            models.UniqueConstraint(
                fields=["scrim", "user"], name="scrim_signup_unique_per_user"
            ),
            models.CheckConstraint(
                condition=models.Q(role_tank=True)
                | models.Q(role_damage=True)
                | models.Q(role_support=True),
                name="scrim_signup_needs_a_role",
            ),
        ]

    def __str__(self):
        return f"{self.user} @ {self.scrim}"

    @property
    def roles(self) -> list[str]:
        return [role for role, field in ROLE_FIELDS.items() if getattr(self, field)]

    @property
    def role_labels(self) -> list[str]:
        labels = dict(Role.choices)
        return [labels[role] for role in self.roles]

    def rating_for(self, role) -> int | None:
        return getattr(self.game_account, RANK_FIELDS[role], None)

    @property
    def best_rating(self) -> int | None:
        """Design 9.4: open formats use the highest rank they filled in."""
        scores = [self.rating_for(role) for role in self.roles if self.rating_for(role)]
        return max(scores) if scores else None
