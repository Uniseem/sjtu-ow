"""Comment moderation in the Wagtail admin (design 14.1, 14.2).

Only 隐藏 and 置顶 (5.6). Round 115: Wagtail's own 添加 (a form that could
never save) and 删除 (a hard delete taking the replies along) are off, the
edit page shows the comment itself, and the list says 是/否 with icons.
"""

from django.urls import reverse
from wagtail import hooks
from wagtail.admin.menu import MenuItem
from wagtail.admin.panels import FieldPanel
from wagtail.admin.ui.tables import BooleanColumn
from wagtail.admin.views import generic
from wagtail.admin.viewsets.model import ModelViewSet
from wagtail.permission_policies import ModelPermissionPolicy
from wagtail.permissions import register_permission_policy

from comments import services
from comments.models import Comment


class CommentPermissionPolicy(ModelPermissionPolicy):
    """Hide and pin only: nobody adds or deletes comments here."""

    def user_has_permission(self, user, action):
        if action in ("add", "delete"):
            return False
        return super().user_has_permission(user, action)

    def user_has_permission_for_instance(self, user, action, instance):
        if action in ("add", "delete"):
            return False
        return super().user_has_permission_for_instance(user, action, instance)


register_permission_policy(Comment, CommentPermissionPolicy(Comment))


class CommentIndexView(generic.IndexView):
    def get_base_queryset(self):
        return super().get_base_queryset().select_related("author", "page")


class CommentEditView(generic.EditView):
    def get_form_class(self):
        base = super().get_form_class()

        class CommentAdminForm(base):
            def clean(self):
                data = super().clean()
                if data.get("is_pinned"):
                    problem = services.pin_problem(
                        self.instance, hidden=data.get("is_hidden")
                    )
                    if problem:
                        self.add_error("is_pinned", problem)
                return data

        return CommentAdminForm

    def save_instance(self):
        if self.form.cleaned_data.get("is_pinned"):
            services.release_pin(self.form.instance.page_id, keep=self.form.instance.pk)
        instance = super().save_instance()
        services.refresh_page(instance.page)  # hidden or pinned: the page changes
        return instance


class CommentViewSet(ModelViewSet):
    model = Comment
    name = "comments"
    icon = "comment"
    menu_label = "评论"
    add_to_admin_menu = False
    copy_view_enabled = False
    inspect_view_enabled = True
    index_view_class = CommentIndexView
    edit_view_class = CommentEditView
    list_display = [
        "short_body",
        "author",
        "page",
        "created_at",
        BooleanColumn("is_hidden", label="已隐藏", sort_key="is_hidden"),
        BooleanColumn("is_pinned", label="置顶", sort_key="is_pinned"),
    ]
    list_filter = ["is_hidden", "is_pinned", "page"]
    search_fields = ["body"]
    panels = [
        FieldPanel("body", read_only=True),
        FieldPanel("author", read_only=True),
        FieldPanel("page", read_only=True),
        FieldPanel("created_at", read_only=True),
        FieldPanel("is_hidden"),
        FieldPanel("is_pinned"),
    ]
    ordering = ["-created_at"]


@hooks.register("register_admin_viewset")
def register_comment_viewset():
    return CommentViewSet()


class CommentMenuItem(MenuItem):
    def is_shown(self, request):
        return services.can_moderate(request.user)


@hooks.register("register_community_menu_item")
def register_comment_menu_item():
    return CommentMenuItem(
        "评论",
        reverse("comments:index"),
        icon_name="comment",
        order=170,
    )
