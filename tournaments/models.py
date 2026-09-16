"""Tournaments (design 8.1, 12.8.1)."""

from django.conf import settings
from django.db import models
from django.utils import timezone
from wagtail.fields import RichTextField


class ReviewMode(models.TextChoices):
    LOCAL = "local", "本站审核"
    UPSTREAM = "upstream", "上游审核"
    TWO_STAGE = "two_stage", "两级审核"


class TournamentStatus(models.TextChoices):
    DRAFT = "draft", "草稿"
    PUBLISHED = "published", "已发布"
    FINISHED = "finished", "已结束"
    CANCELLED = "cancelled", "已取消"


class Tournament(models.Model):
    title = models.CharField("标题", max_length=100)
    summary = models.CharField("简介", max_length=300, blank=True)
    description = RichTextField(
        "详细说明",
        blank=True,
        features=["h2", "h3", "bold", "italic", "ol", "ul", "link", "hr"],
    )
    cover = models.ForeignKey(
        "wagtailimages.Image",
        verbose_name="封面",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="+",
    )
    starts_at = models.DateTimeField("比赛时间", null=True, blank=True)
    registration_opens_at = models.DateTimeField("报名开始时间")
    registration_closes_at = models.DateTimeField("报名截止时间")
    roster_min = models.PositiveSmallIntegerField("参赛人数下限", default=5)
    roster_max = models.PositiveSmallIntegerField("参赛人数上限", default=6)
    sjtu_only = models.BooleanField("仅限交大", default=False)
    review_mode = models.CharField(
        "审核模式",
        max_length=16,
        choices=ReviewMode.choices,
        default=ReviewMode.LOCAL,
    )
    status = models.CharField(
        "状态",
        max_length=16,
        choices=TournamentStatus.choices,
        default=TournamentStatus.DRAFT,
    )
    # M5: source_client = FK to integrations.ApiClient. The table does not
    # exist yet, so the upstream identity is kept as a plain reference.
    external_id = models.CharField("上游赛事 ID", max_length=64, blank=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        verbose_name="创建人",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="+",
    )
    published_at = models.DateTimeField("首次发布时间", null=True, blank=True)
    created_at = models.DateTimeField("创建时间", auto_now_add=True)
    updated_at = models.DateTimeField("更新时间", auto_now=True)

    class Meta:
        verbose_name = "赛事"
        verbose_name_plural = "赛事"
        ordering = ["-registration_opens_at", "-id"]
        constraints = [
            models.CheckConstraint(
                condition=models.Q(roster_min__gte=1)
                & models.Q(roster_max__lte=20)
                & models.Q(roster_min__lte=models.F("roster_max")),
                name="tournament_roster_range",
            ),
            models.CheckConstraint(
                condition=models.Q(
                    registration_opens_at__lt=models.F("registration_closes_at")
                ),
                name="tournament_registration_window",
            ),
            models.UniqueConstraint(
                fields=["external_id"],
                condition=~models.Q(external_id=""),
                name="tournament_external_id_unique",
            ),
        ]

    def __str__(self):
        return self.title

    def get_absolute_url(self) -> str:
        return f"/tournaments/{self.pk}/"

    @property
    def is_public(self) -> bool:
        """Draft tournaments are not reachable from the front end (design 8.2)."""
        return self.status in (
            TournamentStatus.PUBLISHED,
            TournamentStatus.FINISHED,
            TournamentStatus.CANCELLED,
        )

    @property
    def is_listed(self) -> bool:
        return self.status in (TournamentStatus.PUBLISHED, TournamentStatus.FINISHED)

    def phase(self, now=None) -> str:
        """Which group the tournament belongs to on the list page (design 8.2)."""
        now = now or timezone.now()
        if self.status == TournamentStatus.FINISHED:
            return "finished"
        if self.status == TournamentStatus.CANCELLED:
            return "cancelled"
        if now < self.registration_opens_at:
            return "upcoming"
        if now <= self.registration_closes_at:
            return "open"
        return "closed"

    def registration_open(self, now=None) -> bool:
        return self.status == TournamentStatus.PUBLISHED and self.phase(now) == "open"


class RegistrationStatus(models.TextChoices):
    PENDING = "pending", "待审核"
    AWAITING_UPSTREAM = "awaiting_upstream", "待上游确认"
    APPROVED = "approved", "已通过"
    REJECTED = "rejected", "已驳回"
    WITHDRAWN = "withdrawn", "已撤回"


# Statuses whose roster takes up a place in the tournament (design 8.5).
ACTIVE_STATUSES = (
    RegistrationStatus.PENDING,
    RegistrationStatus.AWAITING_UPSTREAM,
    RegistrationStatus.APPROVED,
)


class RegistrationAction(models.TextChoices):
    SUBMIT = "submit", "提交报名"
    RESUBMIT = "resubmit", "重新提交"
    SYNC_ROSTER = "sync_roster", "同步名单"
    APPROVE = "approve", "通过"
    REJECT = "reject", "驳回"
    REVOKE = "revoke", "撤销通过"
    WITHDRAW = "withdraw", "撤回"


class ActorType(models.TextChoices):
    CAPTAIN = "captain", "队长"
    ADMIN = "admin", "本站管理员"
    UPSTREAM = "upstream", "上游"
    SYSTEM = "system", "系统"


class Registration(models.Model):
    """One team's registration for one tournament (design 12.8.2)."""

    tournament = models.ForeignKey(
        Tournament,
        verbose_name="赛事",
        on_delete=models.CASCADE,
        related_name="registrations",
    )
    team = models.ForeignKey(
        "teams.Team",
        verbose_name="战队",
        on_delete=models.PROTECT,
        related_name="registrations",
    )
    status = models.CharField(
        "状态",
        max_length=24,
        choices=RegistrationStatus.choices,
        default=RegistrationStatus.PENDING,
    )
    team_name = models.CharField("战队名称快照", max_length=16)
    roster_version = models.PositiveIntegerField("名单版本", default=1)
    submitted_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        verbose_name="提交人",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="+",
    )
    submitted_at = models.DateTimeField("提交时间", default=timezone.now)
    status_note = models.CharField("最近一次审核备注", max_length=300, blank=True)
    created_at = models.DateTimeField("创建时间", auto_now_add=True)
    updated_at = models.DateTimeField("更新时间", auto_now=True)

    class Meta:
        verbose_name = "报名"
        verbose_name_plural = "报名"
        ordering = ["-submitted_at"]
        constraints = [
            models.UniqueConstraint(
                fields=["tournament", "team"],
                name="unique_registration_per_team",
            )
        ]
        indexes = [
            models.Index(fields=["tournament", "status"]),
            models.Index(fields=["updated_at", "id"]),
        ]

    def __str__(self):
        return f"{self.team_name} · {self.tournament.title}"

    def get_absolute_url(self) -> str:
        return f"/registrations/{self.pk}/"

    @property
    def is_active(self) -> bool:
        return self.status in ACTIVE_STATUSES


class RegistrationMember(models.Model):
    """A frozen copy of one roster entry (design 12.8.3)."""

    registration = models.ForeignKey(
        Registration,
        verbose_name="报名",
        on_delete=models.CASCADE,
        related_name="members",
    )
    tournament = models.ForeignKey(
        Tournament,
        verbose_name="赛事",
        on_delete=models.CASCADE,
        related_name="roster_members",
    )
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        verbose_name="队员",
        on_delete=models.PROTECT,
        related_name="registration_entries",
    )
    game_account = models.ForeignKey(
        "accounts.GameAccount",
        verbose_name="游戏 ID",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="+",
    )
    nickname = models.CharField("昵称快照", max_length=16)
    battletag = models.CharField("游戏 ID 快照", max_length=64)
    is_sjtu = models.BooleanField("是否交大", default=False)
    rank_tank = models.PositiveSmallIntegerField("坦克段位", null=True, blank=True)
    rank_damage = models.PositiveSmallIntegerField("输出段位", null=True, blank=True)
    rank_support = models.PositiveSmallIntegerField("支援段位", null=True, blank=True)
    is_captain = models.BooleanField("是否队长", default=False)
    is_active = models.BooleanField("占名额", default=True)

    class Meta:
        verbose_name = "名单成员"
        verbose_name_plural = "名单成员"
        ordering = ["-is_captain", "nickname"]
        constraints = [
            models.UniqueConstraint(
                fields=["tournament", "user"],
                condition=models.Q(is_active=True),
                name="one_active_roster_per_user_per_tournament",
            )
        ]

    def __str__(self):
        return f"{self.nickname}（{self.battletag}）"


class RegistrationStatusLog(models.Model):
    """Append-only history of a registration (design 12.8.4)."""

    registration = models.ForeignKey(
        Registration,
        verbose_name="报名",
        on_delete=models.CASCADE,
        related_name="logs",
    )
    action = models.CharField("操作", max_length=16, choices=RegistrationAction.choices)
    from_status = models.CharField(
        "变化前状态",
        max_length=24,
        choices=RegistrationStatus.choices,
        blank=True,
    )
    to_status = models.CharField(
        "变化后状态",
        max_length=24,
        choices=RegistrationStatus.choices,
    )
    actor_type = models.CharField("操作方", max_length=16, choices=ActorType.choices)
    actor_user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        verbose_name="操作人",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="+",
    )
    # M5: actor_client = FK to integrations.ApiClient for upstream actions.
    roster_version = models.PositiveIntegerField("名单版本", default=1)
    roster_snapshot = models.JSONField("名单快照", null=True, blank=True)
    note = models.TextField("备注", blank=True)
    created_at = models.DateTimeField("时间", auto_now_add=True)

    class Meta:
        verbose_name = "报名状态日志"
        verbose_name_plural = "报名状态日志"
        ordering = ["created_at", "id"]

    def __str__(self):
        return f"{self.registration_id} {self.get_action_display()}"
