"""Tournaments (design 8.1, 12.8.1)."""

from django.conf import settings
from django.db import models
from django.utils import timezone


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
    description = models.TextField("详细说明", blank=True)
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
