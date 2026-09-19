"""AI moderation records (design 12.14).

The AI only ever writes rows here. Every action on the content itself is done
by a human admin (design 5.5).
"""

from django.db import models


class Risk(models.TextChoices):
    NONE = "none", "无风险"
    LOW = "low", "低"
    MEDIUM = "medium", "中"
    HIGH = "high", "高"
    UNKNOWN = "unknown", "无法判定"


class Category(models.TextChoices):
    ILLEGAL = "illegal", "违法违规"
    PORN = "porn", "色情低俗"
    ATTACK = "attack", "人身攻击"
    POLITICS = "politics", "政治敏感"
    SCAM = "scam", "广告与诈骗"
    GAME_TRADE = "game_trade", "游戏违规交易"
    PRIVACY = "privacy", "泄露他人隐私"
    IMPERSONATION = "impersonation", "冒充官方"
    OTHER = "other", "其他可疑"


class TargetType(models.TextChoices):
    NICKNAME = "nickname", "昵称"
    TEAM_NAME = "team_name", "队名"
    TEAM_DESCRIPTION = "team_description", "战队简介"
    APPLICATION_MESSAGE = "application_message", "入队申请留言"
    ARTICLE = "article", "文章 / 稿件"
    TOURNAMENT_DESCRIPTION = "tournament_description", "赛事说明"
    SCRIM_DESCRIPTION = "scrim_description", "内战说明"
    PAGE = "page", "普通页面"
    IMAGE = "image", "图片"


class ModerationItem(models.Model):
    """One reviewed piece of content (design 12.14.1)."""

    class Status(models.TextChoices):
        PENDING = "pending", "待复核"
        OK = "ok", "无问题"
        HANDLED = "handled", "已处置"
        IGNORED = "ignored", "忽略"

    target_type = models.CharField(
        "内容类型",
        max_length=32,
        choices=TargetType.choices,
    )
    target_id = models.PositiveIntegerField("对象 ID", default=0)
    field = models.CharField("字段", max_length=32, blank=True)
    url = models.CharField("内容地址", max_length=500, blank=True)
    author = models.ForeignKey(
        "accounts.User",
        verbose_name="作者",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="moderation_items",
    )
    excerpt = models.TextField("内容快照")
    text_hash = models.CharField("内容哈希", max_length=64)
    risk = models.CharField(
        "风险等级",
        max_length=16,
        choices=Risk.choices,
        default=Risk.UNKNOWN,
    )
    categories = models.JSONField("命中类别", default=list, blank=True)
    reason = models.TextField("理由", blank=True)
    quote = models.TextField("引用原文", blank=True)
    model = models.CharField("模型", max_length=64, blank=True)
    input_tokens = models.PositiveIntegerField("输入 token", default=0)
    output_tokens = models.PositiveIntegerField("输出 token", default=0)
    status = models.CharField(
        "状态",
        max_length=16,
        choices=Status.choices,
        default=Status.PENDING,
    )
    reviewed_by = models.ForeignKey(
        "accounts.User",
        verbose_name="复核人",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="+",
    )
    reviewed_at = models.DateTimeField("复核时间", null=True, blank=True)
    handling_note = models.CharField("处理说明", max_length=300, blank=True)
    checked_at = models.DateTimeField("审核完成时间", null=True, blank=True)
    notified_at = models.DateTimeField("已通知时间", null=True, blank=True)
    created_at = models.DateTimeField("创建时间", auto_now_add=True)

    class Meta:
        verbose_name = "待复核记录"
        verbose_name_plural = "待复核记录"
        ordering = ["-created_at"]
        constraints = [
            models.UniqueConstraint(
                fields=["target_type", "target_id", "field", "text_hash"],
                name="unique_moderation_target_text",
            )
        ]
        indexes = [
            models.Index(fields=["status", "risk", "created_at"]),
            models.Index(fields=["text_hash"]),
        ]

    def __str__(self):
        return (
            f"{self.get_target_type_display()} #{self.target_id}"
            f"（{self.get_risk_display()}）"
        )

    @property
    def needs_review(self) -> bool:
        return self.status == self.Status.PENDING and self.risk != Risk.NONE

    def category_labels(self) -> list[str]:
        labels = dict(Category.choices)
        return [labels.get(item, item) for item in self.categories or []]


class ModerationUsage(models.Model):
    """Per-day call accounting: daily cap and the monthly cost estimate (5.5.3)."""

    date = models.DateField("日期", unique=True)
    calls = models.PositiveIntegerField("调用次数", default=0)
    items = models.PositiveIntegerField("送审条数", default=0)
    input_tokens = models.PositiveBigIntegerField("输入 token", default=0)
    output_tokens = models.PositiveBigIntegerField("输出 token", default=0)

    class Meta:
        verbose_name = "审核用量"
        verbose_name_plural = "审核用量"
        ordering = ["-date"]

    def __str__(self):
        return f"{self.date}：{self.calls} 次"
