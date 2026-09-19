"""成员分组 in the admin, for superusers and content editors (design 14.1, 14.2)."""

from wagtail.snippets.models import register_snippet
from wagtail.snippets.views.snippets import SnippetViewSet

from members.models import MemberGroup


class MemberGroupViewSet(SnippetViewSet):
    model = MemberGroup
    icon = "group"
    menu_label = "成员分组"
    menu_name = "member_groups"
    menu_order = 260
    add_to_admin_menu = True
    list_display = ["name", "description", "is_visible", "sort_order"]
    ordering = ["sort_order", "name"]
    copy_view_enabled = False


register_snippet(MemberGroupViewSet)
