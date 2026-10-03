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
    # Shown with 「招募中」 (design-details 5.2, v5.2); empty means any.
    recruiting_roles = models.CharField(
        "缺的位置", max_length=32, blank=True, help_text="位置代码，逗号分隔。"
    )
    # Design 7.1 (v6.31): for the members only, never on the static page.
    member_contact = models.CharField(
        "队内联系方式",
        max_length=100,
        blank=True,
        help_text="比如队伍 QQ 群号。只有本队成员看得到，入队通过的邮件里也会写上。",
    )
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

    @property
    def wanted_roles(self) -> list[tuple[str, str]]:
        """(code, label) of the positions the team is short of, while it
        recruits; empty when it takes anyone or is not recruiting."""
        from accounts.roles import ROLE_LABELS, parse_roles

        if not self.is_recruiting:
            return []
        return [
            (role, ROLE_LABELS[role]) for role in parse_roles(self.recruiting_roles)
        ]


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
    role_tank = models.BooleanField("坦克", default=False)
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
            labels.append("坦克")
        if self.role_damage:
            labels.append("输出")
        if self.role_support:
            labels.append("支援")
        return labels


class LeaveReason(models.TextChoices):
    LEFT = "left", "退出"
    REMOVED = "removed", "被移除"


class TeamAlumnus(models.Model):
    """Someone who used to be on the roster: 退役成员 (design-details 5.4).

    Written when a member leaves or is removed; not when the team disbands.
    Deleted when they rejoin, when they or the captain take it off the list,
    and with their account.
    """

    team = models.ForeignKey(
        Team, verbose_name="战队", on_delete=models.CASCADE, related_name="alumni"
    )
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        verbose_name="成员",
        on_delete=models.CASCADE,
        related_name="team_alumni",
    )
    role = models.CharField("离队时的身份", max_length=16, choices=TeamRole.choices)
    joined_at = models.DateTimeField("入队时间")
    left_at = models.DateTimeField("离队时间")
    reason = models.CharField("离队方式", max_length=16, choices=LeaveReason.choices)

    class Meta:
        verbose_name = "退役成员"
        verbose_name_plural = "退役成员"
        ordering = ["-left_at"]
        constraints = [
            models.UniqueConstraint(
                fields=["team", "user"], name="unique_team_alumnus"
            ),
        ]

    def __str__(self):
        return f"{self.team.name} · {self.user.nickname}（退役）"
