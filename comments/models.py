"""Article comments (design 5.6, 12.15).

YouTube-shaped: top-level comments, each with a flat thread of replies.
A reply to a reply lands in the same thread and names who it answers.
"""

from django.conf import settings
from django.db import models

MAX_BODY = 500


class Comment(models.Model):
    page = models.ForeignKey(
        "content.ArticlePage",
        verbose_name="文章",
        on_delete=models.CASCADE,
        related_name="comments",
    )
    author = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        verbose_name="作者",
        on_delete=models.PROTECT,  # users are anonymised, never deleted (3.8)
        related_name="comments",
    )
    parent = models.ForeignKey(
        "self",
        verbose_name="所属顶层评论",
        null=True,
        blank=True,
        on_delete=models.CASCADE,
        related_name="replies",
        help_text="只指向顶层评论；回复的回复仍挂在同一条顶层评论下。",
    )
    reply_to_user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        verbose_name="回复谁",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="+",
    )
    body = models.TextField("内容", max_length=MAX_BODY)
    created_at = models.DateTimeField("时间", auto_now_add=True)
    edited_at = models.DateTimeField("编辑时间", null=True, blank=True)
    is_pinned = models.BooleanField("置顶", default=False)
    is_hidden = models.BooleanField("已隐藏", default=False)
    is_deleted = models.BooleanField("作者已删除", default=False)
    like_count = models.PositiveIntegerField("赞数", default=0)

    class Meta:
        verbose_name = "评论"
        verbose_name_plural = "评论"
        ordering = ["created_at", "id"]
        indexes = [
            models.Index(fields=["page", "created_at"]),
            models.Index(fields=["page", "is_pinned", "like_count"]),
        ]

    def __str__(self):
        return f"#{self.pk} {self.body[:20]}"

    def short_body(self):
        return self.body[:40]

    short_body.short_description = "内容"

    @property
    def is_top_level(self) -> bool:
        return self.parent_id is None

    @property
    def visible(self) -> bool:
        return not (self.is_hidden or self.is_deleted)

    @property
    def anchor(self) -> str:
        return f"comment-{self.pk}"
