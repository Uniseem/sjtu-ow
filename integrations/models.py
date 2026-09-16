"""API clients and call logs (design 12.10)."""

from django.db import models
from django.utils import timezone

from core.fields import EncryptedTextField


class Scope(models.TextChoices):
    TOURNAMENTS_READ = "tournaments:read", "读取赛事"
    TOURNAMENTS_WRITE = "tournaments:write", "创建和更新自己推送的赛事"
    REGISTRATIONS_READ = "registrations:read", "读取报名"
    REGISTRATIONS_REVIEW = "registrations:review", "审核报名"


class Include(models.TextChoices):
    TOURNAMENT = "tournament", "报名所属赛事"
    TEAM = "team", "战队"
    MEMBERS = "members", "名单快照"
    MEMBERS_RANKS = "members.ranks", "名单里的段位"
    LOGS = "logs", "状态日志"


class WebhookPayloadMode(models.TextChoices):
    THIN = "thin", "只带 ID"
    FULL = "full", "带完整对象"


class ApiClient(models.Model):
    """One upstream integration (design 12.10.1)."""

    name = models.CharField("上游名称", max_length=64)
    key_id = models.CharField("Key ID", max_length=32, unique=True)
    secret = EncryptedTextField(
        "Secret",
        help_text="加密存储；验签需要原文，所以不能只存哈希。",
    )
    scopes = models.JSONField("授权范围", default=list, blank=True)
    allowed_includes = models.JSONField("允许的展开项", default=list, blank=True)
    rate_limit_per_minute = models.PositiveIntegerField("每分钟限流", default=600)
    webhook_url = models.URLField("Webhook 地址", blank=True)
    webhook_secret = EncryptedTextField("Webhook 密钥", blank=True)
    webhook_events = models.JSONField("订阅的事件", default=list, blank=True)
    webhook_payload_mode = models.CharField(
        "Webhook 内容",
        max_length=8,
        choices=WebhookPayloadMode.choices,
        default=WebhookPayloadMode.THIN,
    )
    is_active = models.BooleanField("启用", default=True)
    last_used_at = models.DateTimeField("最近使用", null=True, blank=True)
    revoked_at = models.DateTimeField("吊销时间", null=True, blank=True)
    created_at = models.DateTimeField("创建时间", auto_now_add=True)

    class Meta:
        verbose_name = "API 客户端"
        verbose_name_plural = "API 客户端"
        ordering = ["name"]

    def __str__(self):
        return f"{self.name}（{self.key_id}）"

    @property
    def usable(self) -> bool:
        return self.is_active and self.revoked_at is None

    def has_scope(self, scope: str) -> bool:
        return scope in (self.scopes or [])

    def allows_include(self, include: str) -> bool:
        return include in (self.allowed_includes or [])

    def touch(self) -> None:
        ApiClient.objects.filter(pk=self.pk).update(last_used_at=timezone.now())


class ApiRequestLog(models.Model):
    """One API call. No bodies are stored; kept for 90 days (design 12.10.2)."""

    client = models.ForeignKey(
        ApiClient,
        verbose_name="客户端",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="request_logs",
    )
    request_id = models.CharField("请求 ID", max_length=64)
    method = models.CharField("方法", max_length=8)
    path = models.CharField("路径", max_length=500)
    status_code = models.PositiveSmallIntegerField("状态码")
    error_code = models.CharField("错误码", max_length=64, blank=True)
    ip = models.CharField("来源 IP", max_length=64, blank=True)
    duration_ms = models.PositiveIntegerField("耗时（毫秒）", default=0)
    created_at = models.DateTimeField("时间", auto_now_add=True)

    class Meta:
        verbose_name = "API 调用日志"
        verbose_name_plural = "API 调用日志"
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["client", "-created_at"]),
            models.Index(fields=["created_at"]),
        ]

    def __str__(self):
        return f"{self.method} {self.path} → {self.status_code}"
