"""Site-wide models: health probe and Wagtail generic settings (design 12.4.1)."""

from django.core.exceptions import ValidationError
from django.db import models
from wagtail.admin.panels import FieldPanel, MultiFieldPanel
from wagtail.contrib.settings.models import BaseGenericSetting, register_setting

from core.fields import EncryptedTextField


def https_only(value: str) -> None:
    """Links we publish on the homepage must not be http:// or a script (5.2)."""
    if value and not value.lower().startswith("https://"):
        raise ValidationError("只能填 https:// 开头的链接。")


class HealthProbe(models.Model):
    """Dedicated table for /healthz write probes (design 16.6). Rows are rolled back."""

    token = models.CharField(max_length=32)

    class Meta:
        verbose_name = "健康检查探针"
        verbose_name_plural = "健康检查探针"


@register_setting(icon="mail")
class SiteSettings(BaseGenericSetting):
    """Singleton site settings. SMTP is used now; other fields wait for later."""

    select_related = ["default_share_image", "hero_image"]

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
    smtp_password = EncryptedTextField(
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
        help_text="用于页面描述和链接预览。",
    )
    default_share_image = models.ForeignKey(
        "wagtailimages.Image",
        verbose_name="默认分享图片",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="+",
        help_text="没有封面的页面使用这张图作为分享预览。",
    )
    hero_image = models.ForeignKey(
        "wagtailimages.Image",
        verbose_name="首屏图片",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="+",
        help_text="首页最上面的大图，建议 2400×1000 以上；空着时显示深色底和校徽。",
    )
    founded_on = models.DateField(
        "社区成立日期",
        null=True,
        blank=True,
        help_text="首页数字条「社区已成立 N 年 M 天」按它算；空着不显示这一项。",
    )
    qq_group_url = models.URLField(
        "QQ 群链接",
        blank=True,
        validators=[https_only],
        help_text=(
            "QQ 群的分享链接，https:// 开头。"
            "首页首屏的「加入 QQ 群」按钮链接到这里；空着不显示。"
        ),
    )
    team_max_members = models.PositiveIntegerField(
        "战队人数上限",
        default=10,
        help_text="一支战队最多多少人，含队长。",
    )
    team_max_captained = models.PositiveIntegerField(
        "每人最多担任队长数",
        default=3,
        help_text="每人最多同时担任几支战队的队长。",
    )
    max_game_accounts = models.PositiveIntegerField(
        "每人最多游戏 ID",
        default=5,
    )
    scrim_reminder_hours = models.PositiveIntegerField(
        "内战提前提醒小时数",
        default=2,
        help_text="内战开始前多久给报名者发提醒邮件。",
    )
    # Off-site backups (design 16.7). The S3 credentials live here because
    # they are what you need to *reach* the bucket; losing them with the
    # database is fine, you re-enter them on the new server. The encryption
    # key deliberately does not live here — see BACKUP_ENCRYPTION_KEY.
    backup_s3_enabled = models.BooleanField(
        "备份上传到对象存储",
        default=False,
        help_text="开启后，每次备份完会加密并上传一份。需要先设好下面几项。",
    )
    backup_s3_endpoint = models.URLField(
        "对象存储地址",
        blank=True,
        help_text="Cloudflare R2 形如 https://<账号ID>.r2.cloudflarestorage.com",
    )
    backup_s3_bucket = models.CharField("存储桶", max_length=64, blank=True)
    backup_s3_region = models.CharField(
        "区域", max_length=32, blank=True, default="auto", help_text="R2 填 auto。"
    )
    backup_s3_access_key_id = models.CharField(
        "Access Key ID", max_length=128, blank=True
    )
    backup_s3_secret_access_key = EncryptedTextField(
        "Secret Access Key",
        blank=True,
        help_text="加密存储。",
    )
    backup_s3_prefix = models.CharField(
        "路径前缀",
        max_length=128,
        blank=True,
        default="sjtu-ow/",
        help_text="存到桶里的哪个目录下。",
    )
    moderation_enabled = models.BooleanField(
        "启用 AI 内容审核",
        default=True,
        help_text="关掉后新内容不再送审。没有配置 MODERATION_API_KEY 时本来就不送审。",
    )
    moderation_model = models.CharField(
        "审核模型",
        max_length=100,
        default="deepseek-v4.1-flash",
        help_text="服务商接口里的模型名。",
    )
    moderation_daily_limit = models.PositiveIntegerField(
        "审核每日调用上限",
        default=2000,
        help_text="每天最多调用多少次审核接口，超出的内容记为「无法判定」转人工。",
    )
    moderation_image_enabled = models.BooleanField(
        "连图片一起审核",
        default=False,
        help_text="开启后投稿里的图片也送审，费用更高。",
    )
    moderation_high_risk_notify = models.CharField(
        "高风险内容通知",
        max_length=16,
        choices=HighRiskNotify.choices,
        default=HighRiskNotify.IMMEDIATE,
        help_text="AI 判为高风险的内容什么时候邮件通知管理员。",
    )
    font_css_path = models.CharField(
        "字体样式表地址",
        max_length=500,
        blank=True,
        help_text="由「设置 → 排版设置」自动生成。",
    )
    font_css_generated_at = models.DateTimeField(
        "字体样式表生成时间",
        blank=True,
        null=True,
        help_text="由「设置 → 排版设置」自动生成。",
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
                FieldPanel("hero_image"),
                FieldPanel("founded_on"),
                FieldPanel("qq_group_url"),
            ],
            heading="站点信息",
        ),
        MultiFieldPanel(
            [
                FieldPanel("team_max_members"),
                FieldPanel("team_max_captained"),
                FieldPanel("max_game_accounts"),
                FieldPanel("scrim_reminder_hours"),
            ],
            heading="社区参数",
        ),
        MultiFieldPanel(
            [
                FieldPanel("moderation_enabled"),
                FieldPanel("moderation_model"),
                FieldPanel("moderation_daily_limit"),
                FieldPanel("moderation_image_enabled"),
                FieldPanel("moderation_high_risk_notify"),
            ],
            heading="AI 审核",
        ),
        MultiFieldPanel(
            [
                FieldPanel("backup_s3_enabled"),
                FieldPanel("backup_s3_endpoint"),
                FieldPanel("backup_s3_bucket"),
                FieldPanel("backup_s3_region"),
                FieldPanel("backup_s3_access_key_id"),
                FieldPanel("backup_s3_secret_access_key"),
                FieldPanel("backup_s3_prefix"),
            ],
            heading="异地备份（对象存储）",
        ),
    ]

    class Meta:
        verbose_name = "全站设置"


class FontFamily(models.Model):
    """A font in the site font library (design 12.4.3)."""

    class Source(models.TextChoices):
        UPLOAD = "upload", "上传"
        GOOGLE_FONTS = "google_fonts", "Google Fonts"
        URL = "url", "网址下载"

    class License(models.TextChoices):
        OPEN_SOURCE = "open_source", "开源授权"
        WEB_LICENSE = "web_license", "已购买网页嵌入授权"
        OTHER = "other", "其他"

    name = models.CharField("显示名称", max_length=64)
    css_name = models.CharField(
        "样式表字体名",
        max_length=32,
        unique=True,
        help_text="生成样式表时使用，自动分配。",
    )
    source = models.CharField("来源", max_length=16, choices=Source.choices)
    source_ref = models.CharField(
        "来源标识",
        max_length=500,
        blank=True,
        help_text="Google Fonts 字体名称或下载地址。",
    )
    license_type = models.CharField("授权类型", max_length=16, choices=License.choices)
    license_note = models.TextField("授权说明", blank=True)
    license_confirmed = models.BooleanField("已确认允许嵌入网站", default=False)
    created_by = models.ForeignKey(
        "accounts.User",
        verbose_name="添加人",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="+",
    )
    created_at = models.DateTimeField("添加时间", auto_now_add=True)

    class Meta:
        verbose_name = "字体"
        verbose_name_plural = "字体"
        ordering = ["name"]

    def __str__(self):
        return self.name

    def used_by_regions(self):
        """Typography regions referencing this font; they block deletion (13.12.1)."""
        return list(
            TypographyRule.objects.filter(
                family=self, mode=TypographyRule.Mode.CUSTOM
            ).values_list("region", flat=True)
        )

    def ready_faces(self):
        return self.faces.filter(status=FontFace.Status.READY).order_by(
            "weight", "style"
        )


def font_original_upload_path(instance, filename):
    return f"fonts/{instance.family_id}/original/{filename}"


class FontFace(models.Model):
    """One weight/style of a font, plus its processing result (design 12.4.4)."""

    class Style(models.TextChoices):
        NORMAL = "normal", "正常"
        ITALIC = "italic", "斜体"

    class Status(models.TextChoices):
        PENDING = "pending", "等待处理"
        PROCESSING = "processing", "处理中"
        READY = "ready", "可用"
        FAILED = "failed", "失败"

    WEIGHT_CHOICES = [
        (100, "100 Thin"),
        (200, "200 ExtraLight"),
        (300, "300 Light"),
        (400, "400 Regular"),
        (500, "500 Medium"),
        (600, "600 SemiBold"),
        (700, "700 Bold"),
        (800, "800 ExtraBold"),
        (900, "900 Black"),
    ]

    family = models.ForeignKey(
        FontFamily,
        verbose_name="字体",
        on_delete=models.CASCADE,
        related_name="faces",
    )
    weight = models.PositiveSmallIntegerField("字重", choices=WEIGHT_CHOICES)
    style = models.CharField(
        "样式",
        max_length=8,
        choices=Style.choices,
        default=Style.NORMAL,
    )
    original_file = models.FileField(
        "原始文件",
        upload_to=font_original_upload_path,
        null=True,
        blank=True,
        max_length=500,
    )
    status = models.CharField(
        "状态",
        max_length=16,
        choices=Status.choices,
        default=Status.PENDING,
    )
    progress = models.PositiveSmallIntegerField("处理进度", default=0)
    error = models.TextField("失败原因", blank=True)
    slices = models.JSONField("分片", default=list, blank=True)
    slice_count = models.PositiveIntegerField("分片数量", default=0)
    total_bytes = models.PositiveIntegerField("分片总大小", default=0)
    glyph_count = models.PositiveIntegerField("字符数量", default=0)
    created_at = models.DateTimeField("添加时间", auto_now_add=True)
    updated_at = models.DateTimeField("更新时间", auto_now=True)

    class Meta:
        verbose_name = "字重"
        verbose_name_plural = "字重"
        ordering = ["family", "weight", "style"]
        constraints = [
            models.UniqueConstraint(
                fields=["family", "weight", "style"],
                name="unique_font_face_per_family",
            )
        ]

    def __str__(self):
        return f"{self.family.name} {self.weight} {self.get_style_display()}"

    @property
    def label(self):
        suffix = "" if self.style == self.Style.NORMAL else " 斜体"
        return f"{self.weight}{suffix}"


class TypographyRule(models.Model):
    """One of the nine typography regions (design 12.4.5)."""

    class Region(models.TextChoices):
        BODY = "body", "正文"
        H1 = "h1", "一级标题"
        H2 = "h2", "二级标题"
        H3 = "h3", "三级标题"
        H4 = "h4", "四级标题"
        NAV = "nav", "导航栏"
        BUTTON = "button", "按钮"
        NUMERIC = "numeric", "数字与数据"
        MONO = "mono", "游戏 ID 与代码"

    class Mode(models.TextChoices):
        SYSTEM = "system", "系统字体"
        INHERIT = "inherit", "跟随正文"
        CUSTOM = "custom", "字体库中的字体"

    region = models.CharField(
        "区域",
        max_length=16,
        choices=Region.choices,
        unique=True,
    )
    mode = models.CharField(
        "字体来源",
        max_length=16,
        choices=Mode.choices,
        default=Mode.INHERIT,
    )
    family = models.ForeignKey(
        FontFamily,
        verbose_name="字体",
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="typography_rules",
    )
    weight = models.PositiveSmallIntegerField(
        "字重",
        choices=FontFace.WEIGHT_CHOICES,
        default=400,
    )
    size_rem = models.DecimalField(
        "字号（rem）",
        max_digits=5,
        decimal_places=3,
        null=True,
        blank=True,
    )
    line_height = models.DecimalField(
        "行高（倍）",
        max_digits=4,
        decimal_places=2,
        null=True,
        blank=True,
    )
    letter_spacing_em = models.DecimalField(
        "字间距（em）",
        max_digits=5,
        decimal_places=3,
        null=True,
        blank=True,
    )
    updated_at = models.DateTimeField("更新时间", auto_now=True)

    class Meta:
        verbose_name = "排版区域"
        verbose_name_plural = "排版区域"

    def __str__(self):
        return self.get_region_display()

    def clean(self):
        from django.core.exceptions import ValidationError

        errors = {}
        if self.region == self.Region.BODY and self.mode == self.Mode.INHERIT:
            errors["mode"] = "正文区域不能选「跟随正文」。"
        if self.mode == self.Mode.CUSTOM:
            if self.family_id is None:
                errors["family"] = "选择「字体库中的字体」时必须指定字体。"
            elif not self.family.faces.filter(
                weight=self.weight,
                style=FontFace.Style.NORMAL,
                status=FontFace.Status.READY,
            ).exists():
                errors["weight"] = (
                    "这个字体没有处理完成的该字重，请先处理或换一个字重。"
                )
        if errors:
            raise ValidationError(errors)


class PrerenderedPage(models.Model):
    """One public page that is, or should be, served as a static file (12.4.6)."""

    class Status(models.TextChoices):
        PENDING = "pending", "等待生成"
        READY = "ready", "已生成"
        FAILED = "failed", "生成失败"

    path = models.CharField("网址路径", max_length=500, unique=True)
    kind = models.CharField("页面类型", max_length=32)
    status = models.CharField(
        "状态",
        max_length=16,
        choices=Status.choices,
        default=Status.PENDING,
    )
    requested_at = models.DateTimeField("最近一次请求生成", null=True, blank=True)
    generated_at = models.DateTimeField("最近一次生成完成", null=True, blank=True)
    content_hash = models.CharField("内容哈希", max_length=64, blank=True)
    bytes = models.PositiveIntegerField("未压缩大小", default=0)
    error = models.TextField("最近一次失败原因", blank=True)

    class Meta:
        verbose_name = "静态页面"
        verbose_name_plural = "静态页面"
        ordering = ["path"]

    def __str__(self):
        return self.path
