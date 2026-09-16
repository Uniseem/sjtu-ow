from django.contrib.auth.base_user import BaseUserManager
from django.contrib.auth.models import AbstractUser, Group
from django.core.exceptions import ValidationError
from django.core.validators import MinLengthValidator
from django.db import models
from django.db.models.functions import Lower
from django.utils import timezone

from accounts.ranks import decode_rank, format_rank


class UserManager(BaseUserManager):
    """Create users that log in with a case-insensitive email address."""

    use_in_migrations = True

    def normalize_email(self, email):
        email = super().normalize_email(email)
        return email.lower() if email else email

    def _create_user(self, email, password, **extra_fields):
        if not email:
            raise ValueError("Users must have an email address.")
        email = self.normalize_email(email)
        user = self.model(email=email, **extra_fields)
        user.set_password(password)
        user.save(using=self._db)
        return user

    def create_user(self, email, password=None, **extra_fields):
        extra_fields.setdefault("is_staff", False)
        extra_fields.setdefault("is_superuser", False)
        return self._create_user(email, password, **extra_fields)

    def create_superuser(self, email, password=None, **extra_fields):
        extra_fields.setdefault("is_staff", True)
        extra_fields.setdefault("is_superuser", True)
        extra_fields.setdefault("is_active", True)
        extra_fields.setdefault("nickname", extra_fields.get("nickname") or "管理员")
        now = timezone.now()
        extra_fields.setdefault("agreed_terms_at", now)
        extra_fields.setdefault("agreed_cross_border_at", now)
        if extra_fields.get("is_staff") is not True:
            raise ValueError("Superuser must have is_staff=True.")
        if extra_fields.get("is_superuser") is not True:
            raise ValueError("Superuser must have is_superuser=True.")
        return self._create_user(email, password, **extra_fields)


class User(AbstractUser):
    """Site user. Email is the login identifier; username is unused."""

    username = None
    email = models.EmailField("邮箱", max_length=254, unique=True)
    nickname = models.CharField(
        "昵称",
        max_length=16,
        validators=[MinLengthValidator(2)],
    )
    is_sjtu = models.BooleanField("是否来自交大", default=False)
    sjtu_verified_via = models.CharField(
        "交大认证方式",
        max_length=32,
        blank=True,
        null=True,
    )
    sjtu_verified_at = models.DateTimeField("交大认证时间", blank=True, null=True)
    agreed_terms_at = models.DateTimeField("同意用户协议时间")
    agreed_cross_border_at = models.DateTimeField("同意跨境存储时间")
    deactivation_note = models.CharField("停用原因", max_length=200, blank=True)

    objects = UserManager()

    USERNAME_FIELD = "email"
    REQUIRED_FIELDS = ["nickname"]

    class Meta:
        verbose_name = "用户"
        verbose_name_plural = "用户"
        constraints = [
            models.UniqueConstraint(
                Lower("email"),
                name="accounts_user_email_ci_unique",
            ),
        ]

    def __str__(self):
        return self.nickname or self.email


class Feature(models.TextChoices):
    LFG_POST = "lfg_post", "在组队大厅发车"
    TEAM_CREATE = "team_create", "创建战队"
    TEAM_APPLY = "team_apply", "申请加入战队"
    TOURNAMENT_REGISTER = "tournament_register", "报名赛事"
    SCRIM_SIGNUP = "scrim_signup", "报名内战"
    ARTICLE_SUBMIT = "article_submit", "投稿"


BATTLTAG_TAKEN = "该游戏 ID 已被其他账号绑定，如有疑问请联系管理员"


def validate_battletag(value: str) -> None:
    tag = (value or "").strip()
    if tag.count("#") != 1:
        raise ValidationError("游戏 ID 格式为「名称#数字」。")
    name, digits = tag.split("#")
    if " " in name or not name or "#" in name:
        raise ValidationError("名称不能包含空格或 #。")
    if not (2 <= len(name) <= 12):
        raise ValidationError("名称长度必须是 2 到 12 个字符。")
    if not digits.isdigit() or not (4 <= len(digits) <= 6):
        raise ValidationError("数字部分必须是 4 到 6 位数字。")


class GameAccount(models.Model):
    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name="game_accounts",
        verbose_name="用户",
    )
    battletag = models.CharField("游戏 ID", max_length=64)
    rank_tank = models.SmallIntegerField("坦克段位", blank=True, null=True)
    rank_damage = models.SmallIntegerField("输出段位", blank=True, null=True)
    rank_support = models.SmallIntegerField("支援段位", blank=True, null=True)
    ranks_updated_at = models.DateTimeField("段位更新时间", default=timezone.now)

    class Meta:
        verbose_name = "游戏 ID"
        verbose_name_plural = "游戏 ID"
        constraints = [
            models.UniqueConstraint(
                Lower("battletag"),
                name="accounts_gameaccount_battletag_ci_unique",
                violation_error_message=BATTLTAG_TAKEN,
            ),
        ]

    def __str__(self):
        return self.battletag

    def clean(self):
        super().clean()
        self.battletag = (self.battletag or "").strip()
        try:
            validate_battletag(self.battletag)
        except ValidationError as exc:
            raise ValidationError({"battletag": exc.messages}) from exc
        for field in ("rank_tank", "rank_damage", "rank_support"):
            score = getattr(self, field)
            if score is not None:
                try:
                    decode_rank(score)
                except ValueError as exc:
                    raise ValidationError({field: str(exc)}) from exc
        qs = type(self).objects.filter(battletag__iexact=self.battletag)
        if self.pk:
            qs = qs.exclude(pk=self.pk)
        if qs.exists():
            raise ValidationError({"battletag": BATTLTAG_TAKEN})

    def save(self, *args, **kwargs):
        rank_fields = ("rank_tank", "rank_damage", "rank_support")
        if not self._state.adding and self.pk:
            previous = (
                type(self).objects.filter(pk=self.pk).values(*rank_fields).first()
            )
            if previous and any(
                previous[name] != getattr(self, name) for name in rank_fields
            ):
                self.ranks_updated_at = timezone.now()
        if not self.ranks_updated_at:
            self.ranks_updated_at = timezone.now()
        super().save(*args, **kwargs)

    @property
    def tank_label(self) -> str:
        return format_rank(self.rank_tank)

    @property
    def damage_label(self) -> str:
        return format_rank(self.rank_damage)

    @property
    def support_label(self) -> str:
        return format_rank(self.rank_support)


class ContactType(models.TextChoices):
    QQ = "qq", "QQ"
    WECHAT = "wechat", "微信"
    PHONE = "phone", "手机号"
    OTHER = "other", "其他"


def validate_contact_value(contact_type: str, value: str) -> None:
    text = (value or "").strip()
    if contact_type == ContactType.QQ:
        if not text.isdigit() or not (5 <= len(text) <= 11):
            raise ValidationError("QQ 号必须是 5 到 11 位数字。")
    elif contact_type == ContactType.WECHAT:
        if not (6 <= len(text) <= 20):
            raise ValidationError("微信号必须是 6 到 20 个字符。")
    elif contact_type == ContactType.PHONE:
        if not (len(text) == 11 and text.startswith("1") and text.isdigit()):
            raise ValidationError("手机号必须是 11 位中国大陆手机号。")
    elif contact_type == ContactType.OTHER:
        if not text or len(text) > 64:
            raise ValidationError("其他联系方式最多 64 个字符。")
    else:
        raise ValidationError("未知的联系方式类型。")


class ContactMethod(models.Model):
    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name="contact_methods",
        verbose_name="用户",
    )
    type = models.CharField("类型", max_length=16, choices=ContactType.choices)
    value = models.CharField("内容", max_length=64)

    class Meta:
        verbose_name = "联系方式"
        verbose_name_plural = "联系方式"
        constraints = [
            models.UniqueConstraint(
                "user",
                "type",
                name="accounts_contactmethod_user_type_unique",
                violation_error_message="每种联系方式只能填写一次。",
            ),
        ]

    def __str__(self):
        return f"{self.get_type_display()} {self.value}"

    def clean(self):
        super().clean()
        self.value = (self.value or "").strip()
        try:
            validate_contact_value(self.type, self.value)
        except ValidationError as exc:
            raise ValidationError({"value": exc.messages}) from exc


class FeatureGroupRestriction(models.Model):
    group = models.ForeignKey(
        Group,
        on_delete=models.CASCADE,
        related_name="feature_restrictions",
        verbose_name="用户组",
    )
    feature = models.CharField("功能", max_length=32, choices=Feature.choices)
    note = models.CharField("原因", max_length=200, blank=True)
    updated_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="feature_group_restriction_updates",
        verbose_name="操作人",
    )

    class Meta:
        verbose_name = "用户组功能限制"
        verbose_name_plural = "用户组功能限制"
        constraints = [
            models.UniqueConstraint(
                "group",
                "feature",
                name="accounts_featuregrouprestriction_unique",
            ),
        ]

    def __str__(self):
        return f"{self.group} · {self.get_feature_display()}"


class FeatureUserRule(models.Model):
    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name="feature_rules",
        verbose_name="用户",
    )
    feature = models.CharField("功能", max_length=32, choices=Feature.choices)
    allowed = models.BooleanField("单独允许", default=False)
    note = models.CharField("原因", max_length=200, blank=True)
    updated_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="feature_user_rule_updates",
        verbose_name="操作人",
    )

    class Meta:
        verbose_name = "用户功能规则"
        verbose_name_plural = "用户功能规则"
        constraints = [
            models.UniqueConstraint(
                "user",
                "feature",
                name="accounts_featureuserrule_unique",
            ),
        ]

    def __str__(self):
        verb = "允许" if self.allowed else "禁止"
        return f"{self.user} · {verb} {self.get_feature_display()}"
