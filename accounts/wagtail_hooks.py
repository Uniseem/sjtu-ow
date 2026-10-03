"""Wagtail admin for feature gates. Superuser only (design 4.3)."""

from django.urls import reverse
from wagtail import hooks
from wagtail.admin.menu import Menu, SubmenuMenuItem
from wagtail.admin.panels import FieldPanel
from wagtail.admin.ui.tables import Column
from wagtail.admin.views import account as wagtail_account
from wagtail.admin.views import generic
from wagtail.admin.viewsets.model import ModelViewSet, ModelViewSetGroup
from wagtail.admin.widgets.button import Button
from wagtail.permission_policies.base import BasePermissionPolicy
from wagtail.permissions import register_permission_policy

from accounts.admin_users import USERS_MENU_HOOK
from accounts.models import FeatureGroupRestriction, FeatureUserRule, User
from accounts.services import GROUP_CONTENT

# The admin account page is open to every admin user, which through 投稿者 is
# every verified member (round 115). Its name panel asks for 名/姓 (the site
# uses nicknames) and its picture panel takes an unreviewed face (design-details
# 2.3), so both are off; the email is handled by WAGTAIL_EMAIL_MANAGEMENT_ENABLED.
wagtail_account.NameEmailSettingsPanel.is_active = lambda self: False
wagtail_account.AvatarSettingsPanel.is_active = lambda self: False


class SuperuserOnlyPolicy(BasePermissionPolicy):
    """Feature restriction UIs are not granted to staff groups."""

    def user_has_permission(self, user, action):
        return bool(getattr(user, "is_superuser", False))

    def users_with_any_permission(self, actions):
        return User.objects.filter(is_superuser=True)


register_permission_policy(
    FeatureGroupRestriction,
    SuperuserOnlyPolicy(FeatureGroupRestriction),
)
register_permission_policy(
    FeatureUserRule,
    SuperuserOnlyPolicy(FeatureUserRule),
)


class StampUpdatedByMixin:
    def save_instance(self):
        self.form.instance.updated_by = self.request.user
        return super().save_instance()


class FeatureCreateView(StampUpdatedByMixin, generic.CreateView):
    pass


class FeatureEditView(StampUpdatedByMixin, generic.EditView):
    pass


class FeatureUserRuleCreateView(FeatureCreateView):
    def get_initial(self):
        initial = super().get_initial()
        user_id = self.request.GET.get("user")
        if user_id:
            initial["user"] = user_id
        return initial


class FeatureUserRuleIndexView(generic.IndexView):
    def get_base_queryset(self):
        qs = super().get_base_queryset()
        user_id = self.request.GET.get("user")
        if user_id:
            qs = qs.filter(user_id=user_id)
        return qs


class FeatureGroupRestrictionViewSet(ModelViewSet):
    model = FeatureGroupRestriction
    name = "feature_group_restrictions"
    icon = "group"
    add_to_admin_menu = False
    copy_view_enabled = False
    list_display = ["group", "feature", "note", "updated_by"]
    search_fields = ["note"]
    form_fields = ["group", "feature", "note"]
    panels = [
        FieldPanel("group"),
        FieldPanel("feature"),
        FieldPanel("note"),
    ]
    add_view_class = FeatureCreateView
    edit_view_class = FeatureEditView


class FeatureUserRuleViewSet(ModelViewSet):
    model = FeatureUserRule
    name = "feature_user_rules"
    icon = "user"
    add_to_admin_menu = False
    copy_view_enabled = False
    list_display = [
        "user",
        "feature",
        Column(
            "allowed",
            label="规则",
            accessor=lambda rule: "单独允许" if rule.allowed else "单独禁止",
            sort_key="allowed",
        ),
        "note",
        "updated_by",
    ]
    search_fields = ["note"]
    form_fields = ["user", "feature", "allowed", "note"]
    panels = [
        FieldPanel("user"),
        FieldPanel("feature"),
        FieldPanel("allowed"),
        FieldPanel("note"),
    ]
    index_view_class = FeatureUserRuleIndexView
    add_view_class = FeatureUserRuleCreateView
    edit_view_class = FeatureEditView


class FeaturePermissionViewSetGroup(ModelViewSetGroup):
    menu_label = "功能权限"
    menu_icon = "lock"
    menu_name = "feature_permissions"
    menu_order = 700
    menu_hook = USERS_MENU_HOOK
    items = (FeatureGroupRestrictionViewSet, FeatureUserRuleViewSet)


@hooks.register("register_admin_viewset")
def register_feature_viewsets():
    return FeaturePermissionViewSetGroup()


@hooks.register("register_user_listing_buttons")
def feature_rule_user_listing_button(user, request_user):
    if not request_user.is_superuser:
        return
    yield Button(
        "功能规则",
        reverse("feature_user_rules:index") + f"?user={user.pk}",
        icon_name="lock",
        priority=50,
    )


users_menu = Menu(
    register_hook_name=USERS_MENU_HOOK,
    construct_hook_name="construct_users_menu",
)


@hooks.register("register_admin_menu_item")
def register_users_menu():
    """「用户」: users, groups and feature permissions, out of 「设置」
    (design 14.1, round 117). Shown when any of them is (superusers)."""
    return SubmenuMenuItem(
        "用户",
        users_menu,
        name="users-menu",
        icon_name="user",
        order=8000,
    )


# Wagtail's own reports and help are for superusers and content editors
# (design 14.1). The report pages filter by Wagtail's object permissions on
# their own, so another role opening one by URL only sees its own objects.
EDITOR_ONLY_MENUS = frozenset({"reports", "help"})


@hooks.register("construct_main_menu")
def hide_reports_and_help(request, menu_items):
    user = request.user
    if user.is_superuser or user.groups.filter(name=GROUP_CONTENT).exists():
        return
    menu_items[:] = [
        item
        for item in menu_items
        if getattr(item, "name", "") not in EDITOR_ONLY_MENUS
    ]
