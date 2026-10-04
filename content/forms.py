"""Admin forms for article pages (design 5.4 / 14.3)."""

from wagtail.admin.forms import WagtailAdminPageForm

from content.permissions import (
    is_submitter_only,
    plain_writer,
    user_can_edit_author,
)

# What the 「推荐」 tab holds: the address, the search text, the menu switch
# and the publishing schedule. Whoever's article goes through review has no
# use for them; the editor sets them when publishing (round 130, design 14.3).
# Left out of the form rather than hidden, so saving again keeps what the
# editor set.
EDITOR_ONLY_FIELDS = (
    "slug",
    "seo_title",
    "search_description",
    "show_in_menus",
    "go_live_at",
    "expire_at",
)


class ArticlePageForm(WagtailAdminPageForm):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        user = self.for_user
        if user is None:
            return
        if "author" in self.fields and not user_can_edit_author(user):
            self.fields.pop("author")
        if "comments_enabled" in self.fields and is_submitter_only(user):
            self.fields.pop("comments_enabled")
        if "category" in self.fields and is_submitter_only(user):
            from content.models import ArticleCategory

            self.fields["category"].queryset = ArticleCategory.objects.filter(
                allow_submission=True
            )
        if plain_writer(user):
            for name in EDITOR_ONLY_FIELDS:
                self.fields.pop(name, None)

    def clean(self):
        cleaned_data = super().clean()
        if "slug" not in self.fields and not self.instance.slug:
            self.instance.slug = self._free_slug(
                cleaned_data.get("title") or self.instance.title or ""
            )
        return cleaned_data

    def _free_slug(self, title: str) -> str:
        """The address the writer would have got from the title, made free:
        Wagtail's own fallback cannot step round the reserved words, and the
        error would land on a field this form does not have."""
        from django.utils.text import slugify
        from wagtail.models import Page

        from content.models import RESERVED_CHILD_SLUGS

        base = slugify(title, allow_unicode=True)[:60] or "article"
        if base.lower() in RESERVED_CHILD_SLUGS:
            base = f"{base}-article"
        candidate, number = base, 1
        while not Page._slug_is_available(candidate, self.parent_page, self.instance):
            number += 1
            candidate = f"{base}-{number}"
        return candidate

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
