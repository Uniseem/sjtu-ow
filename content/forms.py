"""Admin forms for article pages (design 5.4 / 14.3)."""

from wagtail.admin.forms import WagtailAdminPageForm

from content.permissions import is_submitter_only, user_can_edit_author


class ArticlePageForm(WagtailAdminPageForm):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        user = self.for_user
        if user is None:
            return
        if "author" in self.fields and not user_can_edit_author(user):
            self.fields.pop("author")
        if "category" in self.fields and is_submitter_only(user):
            from content.models import ArticleCategory

            self.fields["category"].queryset = ArticleCategory.objects.filter(
                allow_submission=True
            )

    def save(self, commit=True):
        instance = self.instance
        if not instance.author_id:
            if instance.owner_id:
                instance.author_id = instance.owner_id
            elif self.for_user is not None:
                instance.author = self.for_user
                if not instance.owner_id:
                    instance.owner = self.for_user
        return super().save(commit=commit)
