"""Register ArticleCategory as a snippet (design 14.2)."""

from wagtail.snippets.models import register_snippet
from wagtail.snippets.views.snippets import SnippetViewSet

from content.models import ArticleCategory


class ArticleCategoryViewSet(SnippetViewSet):
    model = ArticleCategory
    icon = "tag"
    menu_label = "文章分类"
    menu_name = "article_categories"
    menu_order = 250
    add_to_admin_menu = True
    list_display = ["name", "slug", "sort_order", "allow_submission"]
    search_fields = ["name", "slug"]
    ordering = ["sort_order", "name"]
    copy_view_enabled = False


register_snippet(ArticleCategoryViewSet)
