"""Member groups for the showcase page (design 6.2, 12.7)."""

from django import forms
from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models
from modelcluster.fields import ParentalKey
from modelcluster.models import ClusterableModel
from wagtail.admin.panels import FieldPanel, InlinePanel
from wagtail.models import Orderable


class _MemberChoiceField(forms.ModelChoiceField):
    """Nicknames repeat; the admin picks 「昵称（邮箱）」."""

    def label_from_instance(self, obj):
        return f"{obj.nickname}（{obj.email}）"


class MemberUserField(models.ForeignKey):
    def formfield(self, **kwargs):
        kwargs.setdefault("form_class", _MemberChoiceField)
        return super().formfield(**kwargs)


class MemberGroup(ClusterableModel):
    """An admin-defined group on /members/, such as 「社团干部」."""

    name = models.CharField("名称", max_length=20)
    description = models.CharField("简介", max_length=200, blank=True)
    is_visible = models.BooleanField(
        "显示",
        default=True,
        help_text="不显示的分组不出现在成员展示页上，组里的人仍然在「全部成员」里。",
    )
    sort_order = models.PositiveSmallIntegerField(
        "排序", default=0, help_text="数字小的排在前面。"
    )

    panels = [
        FieldPanel("name"),
        FieldPanel("description"),
        FieldPanel("is_visible"),
        FieldPanel("sort_order"),
        InlinePanel("memberships", label="成员", heading="组里的成员"),
    ]

    class Meta:
        verbose_name = "成员分组"
        verbose_name_plural = "成员分组"
        ordering = ["sort_order", "name"]
        constraints = [
            models.UniqueConstraint(
                models.functions.Lower("name"), name="members_group_name_ci_unique"
            ),
        ]

    def __str__(self):
        return self.name

    def clean(self):
        super().clean()
        name = (self.name or "").strip()
        clash = MemberGroup.objects.filter(name__iexact=name).exclude(pk=self.pk)
        if name and clash.exists():
            raise ValidationError({"name": "已经有同名的分组了。"})


class MemberGroupMembership(Orderable):
    group = ParentalKey(
        MemberGroup, on_delete=models.CASCADE, related_name="memberships"
    )
    user = MemberUserField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="member_groups",
        verbose_name="成员",
        limit_choices_to={"is_active": True},
    )
    title = models.CharField(
        "职务", max_length=20, blank=True, help_text="可选，比如「社长」。"
    )

    panels = [FieldPanel("user"), FieldPanel("title")]

    class Meta(Orderable.Meta):
        verbose_name = "分组成员"
        verbose_name_plural = "分组成员"
        constraints = [
            models.UniqueConstraint(
                fields=["group", "user"], name="members_membership_unique"
            ),
        ]

    def __str__(self):
        return f"{self.group} · {self.user}"

    def clean(self):
        super().clean()
        from members.services import is_joined

        if self.user_id and not is_joined(self.user):
            raise ValidationError(
                {"user": "只能选已加入的用户：账号没有停用，并且验证过邮箱。"}
            )
