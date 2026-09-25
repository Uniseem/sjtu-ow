from django.apps import AppConfig


class CommentsConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "comments"
    verbose_name = "文章评论"

    def ready(self):
        from comments.rendering import article_comments_slot
        from core.slots import register

        register("article-comments", article_comments_slot)
