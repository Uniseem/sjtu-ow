"""Comment moderation in the Wagtail admin (design 14.1, 14.2)."""

from django.urls import reverse
from wagtail import hooks
from wagtail.admin.menu import MenuItem
from wagtail.admin.views import generic
from wagtail.admin.viewsets.model import ModelViewSet

from comments import services
from comments.models import Comment


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
    edit_view_class = CommentEditView
    list_display = [
        "short_body",
        "author",
        "page",
        "created_at",
        "is_hidden",
        "is_pinned",
    ]
    list_filter = ["is_hidden", "is_pinned", "page"]
    search_fields = ["body"]
    form_fields = ["is_hidden", "is_pinned"]
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
