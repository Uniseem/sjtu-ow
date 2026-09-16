from django.contrib.auth.base_user import BaseUserManager
from django.contrib.auth.models import AbstractUser
from django.core.validators import MinLengthValidator
from django.db import models
from django.db.models.functions import Lower
from django.utils import timezone


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
