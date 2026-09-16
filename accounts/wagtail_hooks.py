"""Wagtail admin for feature gates. Superuser only (design 4.3)."""

from django.urls import reverse
from wagtail import hooks
from wagtail.admin.panels import FieldPanel
from wagtail.admin.views import generic
from wagtail.admin.viewsets.model import ModelViewSet, ModelViewSetGroup
from wagtail.admin.widgets.button import Button
from wagtail.permission_policies.base import BasePermissionPolicy
from wagtail.permissions import register_permission_policy

from accounts.models import FeatureGroupRestriction, FeatureUserRule, User


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
    list_display = ["user", "feature", "allowed", "note", "updated_by"]
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
    add_to_admin_menu = False
    add_to_settings_menu = True
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
