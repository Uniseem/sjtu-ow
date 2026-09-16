"""Looking-for-group posts (design 6, 12.7)."""

from django.conf import settings
from django.db import models
from django.utils import timezone


class LfgStatus(models.TextChoices):
    OPEN = "open", "招人中"
    FULL = "full", "已满"
    CLOSED = "closed", "已关闭"


class LfgPost(models.Model):
    owner = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        verbose_name="车主",
        on_delete=models.CASCADE,
        related_name="lfg_posts",
    )
    game_account = models.ForeignKey(
        "accounts.GameAccount",
        verbose_name="游戏 ID",
        on_delete=models.CASCADE,
        related_name="lfg_posts",
    )
    mode = models.ForeignKey(
        "core.GameMode",
        verbose_name="模式",
        on_delete=models.PROTECT,
        related_name="lfg_posts",
    )
    role_tank = models.BooleanField("缺重装", default=False)
    role_damage = models.BooleanField("缺输出", default=False)
    role_support = models.BooleanField("缺支援", default=False)
    start_at = models.DateTimeField("开车时间")
    expires_at = models.DateTimeField("过期时间")
    status = models.CharField(
        "状态",
        max_length=16,
        choices=LfgStatus.choices,
        default=LfgStatus.OPEN,
    )
    note = models.CharField("备注", max_length=200, blank=True)
    created_at = models.DateTimeField("发布时间", auto_now_add=True)
    updated_at = models.DateTimeField("更新时间", auto_now=True)

    class Meta:
        verbose_name = "车帖"
        verbose_name_plural = "车帖"
        ordering = ["start_at", "-created_at"]
        indexes = [models.Index(fields=["expires_at", "status"])]

    def __str__(self):
        return f"{self.owner.nickname} · {self.mode.name}"

    @property
    def is_expired(self) -> bool:
        return self.expires_at <= timezone.now()

    def role_labels(self) -> list[str]:
        labels = []
        if self.role_tank:
            labels.append("重装")
        if self.role_damage:
            labels.append("输出")
        if self.role_support:
            labels.append("支援")
        return labels
