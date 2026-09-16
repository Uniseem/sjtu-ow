"""Teams, memberships and join applications (design 7, 12.6)."""

from django.conf import settings
from django.db import models
from django.db.models.functions import Lower


class TeamRole(models.TextChoices):
    CAPTAIN = "captain", "队长"
    MEMBER = "member", "队员"


class ApplicationStatus(models.TextChoices):
    PENDING = "pending", "待审批"
    APPROVED = "approved", "已通过"
    REJECTED = "rejected", "已拒绝"
    CANCELLED = "cancelled", "已取消"


class Team(models.Model):
    """A team. Disbanding is a soft delete: registrations still point here."""

    name = models.CharField("队名", max_length=16)
    description = models.TextField("简介", max_length=500, blank=True)
    logo = models.ForeignKey(
        "wagtailimages.Image",
        verbose_name="队标",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="+",
    )
    is_recruiting = models.BooleanField("招募中", default=True)
    disbanded_at = models.DateTimeField("解散时间", null=True, blank=True)
    created_at = models.DateTimeField("创建时间", auto_now_add=True)
    updated_at = models.DateTimeField("更新时间", auto_now=True)

    class Meta:
        verbose_name = "战队"
        verbose_name_plural = "战队"
        ordering = ["-created_at"]
        constraints = [
            models.UniqueConstraint(
                Lower("name"),
                condition=models.Q(disbanded_at__isnull=True),
                name="unique_active_team_name",
            )
        ]

    def __str__(self):
        return self.name

    @property
    def is_disbanded(self) -> bool:
        return self.disbanded_at is not None

    def get_absolute_url(self) -> str:
        return f"/teams/{self.pk}/"

    def captain(self):
        membership = self.memberships.filter(role=TeamRole.CAPTAIN).first()
        return membership.user if membership else None

    def member_count(self) -> int:
        return self.memberships.count()


class TeamMembership(models.Model):
    team = models.ForeignKey(
        Team,
        verbose_name="战队",
        on_delete=models.CASCADE,
        related_name="memberships",
    )
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        verbose_name="成员",
        on_delete=models.CASCADE,
        related_name="team_memberships",
    )
    role = models.CharField(
        "身份",
        max_length=16,
        choices=TeamRole.choices,
        default=TeamRole.MEMBER,
    )
    joined_at = models.DateTimeField("入队时间", auto_now_add=True)

    class Meta:
        verbose_name = "战队成员"
        verbose_name_plural = "战队成员"
        ordering = ["role", "joined_at"]
        constraints = [
            models.UniqueConstraint(
                fields=["team", "user"],
                name="unique_team_member",
            ),
            models.UniqueConstraint(
                fields=["team"],
                condition=models.Q(role="captain"),
                name="one_captain_per_team",
            ),
        ]

    def __str__(self):
        return f"{self.team.name} · {self.user.nickname}"

    @property
    def is_captain(self) -> bool:
        return self.role == TeamRole.CAPTAIN


class TeamApplication(models.Model):
    team = models.ForeignKey(
        Team,
        verbose_name="战队",
        on_delete=models.CASCADE,
        related_name="applications",
    )
    applicant = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        verbose_name="申请人",
        on_delete=models.CASCADE,
        related_name="team_applications",
    )
    role_tank = models.BooleanField("重装", default=False)
    role_damage = models.BooleanField("输出", default=False)
    role_support = models.BooleanField("支援", default=False)
    message = models.CharField("留言", max_length=200, blank=True)
    status = models.CharField(
        "状态",
        max_length=16,
        choices=ApplicationStatus.choices,
        default=ApplicationStatus.PENDING,
    )
    decided_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        verbose_name="审批人",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="+",
    )
    decided_at = models.DateTimeField("审批时间", null=True, blank=True)
    decision_note = models.CharField("拒绝原因", max_length=200, blank=True)
    created_at = models.DateTimeField("提交时间", auto_now_add=True)

    class Meta:
        verbose_name = "入队申请"
        verbose_name_plural = "入队申请"
        ordering = ["-created_at"]
        constraints = [
            models.UniqueConstraint(
                fields=["team", "applicant"],
                condition=models.Q(status="pending"),
                name="one_pending_application_per_team",
            )
        ]

    def __str__(self):
        return f"{self.applicant.nickname} → {self.team.name}"

    def role_labels(self) -> list[str]:
        labels = []
        if self.role_tank:
            labels.append("重装")
        if self.role_damage:
            labels.append("输出")
        if self.role_support:
            labels.append("支援")
        return labels
