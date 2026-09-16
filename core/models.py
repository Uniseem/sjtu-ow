"""Site-wide models: health probe and Wagtail generic settings (design 12.4.1)."""

from django.db import models
from wagtail.admin.panels import FieldPanel, MultiFieldPanel
from wagtail.contrib.settings.models import BaseGenericSetting, register_setting

LATER = "后续里程碑使用"


class HealthProbe(models.Model):
    """Dedicated table for /healthz write probes (design 16.6). Rows are rolled back."""

    token = models.CharField(max_length=32)

    class Meta:
        verbose_name = "健康检查探针"
        verbose_name_plural = "健康检查探针"


@register_setting(icon="mail")
class SiteSettings(BaseGenericSetting):
    """Singleton site settings. SMTP is used now; other fields wait for later."""

    select_related = ["default_share_image"]

    class SmtpSecurity(models.TextChoices):
        NONE = "none", "无"
        STARTTLS = "starttls", "STARTTLS"
        SSL = "ssl", "SSL"

    class HighRiskNotify(models.TextChoices):
        IMMEDIATE = "immediate", "立即"
        DAILY = "daily", "每日汇总"

    smtp_host = models.CharField("SMTP 服务器", max_length=255, blank=True)
    smtp_port = models.PositiveIntegerField("SMTP 端口", default=465)
    smtp_security = models.CharField(
        "加密方式",
        max_length=16,
        choices=SmtpSecurity.choices,
        default=SmtpSecurity.SSL,
    )
    smtp_username = models.CharField("SMTP 账号", max_length=255, blank=True)
    smtp_password = models.TextField(
        "SMTP 密码",
        blank=True,
        help_text="加密存储。后台表单不回显原值，留空表示不修改。",
    )
    from_address = models.EmailField("发件地址", blank=True)
    from_name = models.CharField(
        "发件人名称",
        max_length=100,
        default="SJTU 守望先锋社区",
    )
    email_subject_prefix = models.CharField(
        "邮件主题前缀",
        max_length=40,
        default="[SJTU OW]",
    )
    site_description = models.TextField(
        "站点简介",
        blank=True,
        help_text=LATER,
    )
    default_share_image = models.ForeignKey(
        "wagtailimages.Image",
        verbose_name="默认分享图片",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="+",
        help_text=LATER,
    )
    team_max_members = models.PositiveIntegerField(
        "战队人数上限",
        default=10,
        help_text=LATER,
    )
    team_max_captained = models.PositiveIntegerField(
        "每人最多担任队长数",
        default=3,
        help_text=LATER,
    )
    max_game_accounts = models.PositiveIntegerField(
        "每人最多游戏 ID",
        default=5,
        help_text=LATER,
    )
    lfg_max_active_posts = models.PositiveIntegerField(
        "每人最多未过期车帖",
        default=3,
        help_text=LATER,
    )
    lfg_expire_hours = models.PositiveIntegerField(
        "车帖过期小时数",
        default=2,
        help_text=LATER,
    )
    scrim_reminder_hours = models.PositiveIntegerField(
        "内战提前提醒小时数",
        default=2,
        help_text=LATER,
    )
    moderation_enabled = models.BooleanField(
        "启用 AI 内容审核",
        default=True,
        help_text=LATER,
    )
    moderation_model = models.CharField(
        "审核模型",
        max_length=100,
        default="deepseek-v4.1-flash",
        help_text=LATER,
    )
    moderation_daily_limit = models.PositiveIntegerField(
        "审核每日调用上限",
        default=2000,
        help_text=LATER,
    )
    moderation_image_enabled = models.BooleanField(
        "连图片一起审核",
        default=False,
        help_text=LATER,
    )
    moderation_high_risk_notify = models.CharField(
        "高风险内容通知",
        max_length=16,
        choices=HighRiskNotify.choices,
        default=HighRiskNotify.IMMEDIATE,
        help_text=LATER,
    )
    font_css_path = models.CharField(
        "字体样式表地址",
        max_length=500,
        blank=True,
        help_text=LATER,
    )
    font_css_generated_at = models.DateTimeField(
        "字体样式表生成时间",
        blank=True,
        null=True,
        help_text=LATER,
    )

    panels = [
        MultiFieldPanel(
            [
                FieldPanel("smtp_host"),
                FieldPanel("smtp_port"),
                FieldPanel("smtp_security"),
                FieldPanel("smtp_username"),
                FieldPanel("smtp_password"),
                FieldPanel("from_address"),
                FieldPanel("from_name"),
                FieldPanel("email_subject_prefix"),
            ],
            heading="邮件发送",
        ),
        MultiFieldPanel(
            [
                FieldPanel("site_description"),
                FieldPanel("default_share_image"),
            ],
            heading="站点信息（后续里程碑使用）",
        ),
        MultiFieldPanel(
            [
                FieldPanel("team_max_members"),
                FieldPanel("team_max_captained"),
                FieldPanel("max_game_accounts"),
                FieldPanel("lfg_max_active_posts"),
                FieldPanel("lfg_expire_hours"),
                FieldPanel("scrim_reminder_hours"),
            ],
            heading="社区参数（后续里程碑使用）",
        ),
        MultiFieldPanel(
            [
                FieldPanel("moderation_enabled"),
                FieldPanel("moderation_model"),
                FieldPanel("moderation_daily_limit"),
                FieldPanel("moderation_image_enabled"),
                FieldPanel("moderation_high_risk_notify"),
            ],
            heading="AI 审核（后续里程碑使用）",
        ),
        MultiFieldPanel(
            [
                FieldPanel("font_css_path"),
                FieldPanel("font_css_generated_at"),
            ],
            heading="字体（后续里程碑使用）",
        ),
    ]

    class Meta:
        verbose_name = "全站设置"
