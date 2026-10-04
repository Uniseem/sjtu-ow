"""Wagtail's user screens under /wagtail/, for superusers (design 3.7; round
115). Since v7.0 users are edited in the back office (backoffice.views.
members); these stay so the fallback admin keeps the same rules.

Wagtail's own screens ask for 名/姓 and know nothing of this site's people.
Here the account tab has the email, the nickname, 是否来自交大 and, for a
stopped account, why. The edit page also shows what the person has on the
site (game IDs, contacts for those allowed to see them, teams, feature
rules). Nobody is added or deleted from the admin: registering needs the
person's own consent (3.1) and users are never deleted (3.7, 3.8).
"""

from __future__ import annotations

from django import forms
from django.contrib import messages
from django.core.exceptions import PermissionDenied
from wagtail.users.forms import UserEditForm
from wagtail.users.views import users as wagtail_users
from wagtail.users.views.groups import GroupViewSet


class SiteUserEditForm(UserEditForm):
    first_name = None
    last_name = None
    deactivation_note = forms.CharField(
        label="停用原因",
        required=False,
        max_length=200,
        help_text="停用账号时必填，只有管理员能看到（设计 3.7）。",
    )

    class Meta(UserEditForm.Meta):
        fields = (UserEditForm.Meta.fields - {"first_name", "last_name"}) | {
            "nickname",
            "is_sjtu",
            "deactivation_note",
        }

    def clean(self):
        cleaned = super().clean()
        stopping = self.instance.is_active and cleaned.get("is_active") is False
        if stopping and not (cleaned.get("deactivation_note") or "").strip():
            self.add_error("deactivation_note", "停用账号要写原因。")
        return cleaned


class UserIndexView(wagtail_users.IndexView):
    def get_add_url(self):
        return None  # members register themselves (3.1)

    def get_delete_url(self, instance):
        return None  # users are never deleted (3.7)


class UserEditView(wagtail_users.EditView):
    def setup(self, request, *args, **kwargs):
        super().setup(request, *args, **kwargs)
        self.can_delete = False
        self.was_active = self.object.is_active

    def save_instance(self):
        from accounts.services import after_deactivation

        instance = super().save_instance()
        if self.was_active and not instance.is_active:
            from teams.services import captained_teams

            paused = after_deactivation(instance)
            messages.info(
                self.request, "账号已停用：不能再登录，待审批的入队申请已取消。"
            )
            teams = captained_teams(instance)
            if teams:
                names = "、".join(f"「{team.name}」" for team in teams)
                messages.warning(
                    self.request,
                    f"这个账号是{names}的队长，到「成员 → 战队」给这些队指定新队长。",
                )
            if paused:
                names = "、".join(f"「{team.name}」" for team in paused)
                messages.info(
                    self.request,
                    f"{names}已改成暂不招募，新队长可以在战队管理页重新打开。",
                )
        return instance

    def get_context_data(self, **kwargs):
        from accounts.services import admin_profile

        context = super().get_context_data(**kwargs)
        context["profile"] = admin_profile(self.object, viewer=self.request.user)
        return context


class UserCreateView(wagtail_users.CreateView):
    def dispatch(self, request, *args, **kwargs):
        raise PermissionDenied("成员要自己注册（设计 3.1），后台不新建用户。")


class UserDeleteView(wagtail_users.DeleteView):
    def dispatch(self, request, *args, **kwargs):
        raise PermissionDenied("用户不做删除（设计 3.7），要停用请取消「启用」。")


class SiteUserViewSet(wagtail_users.UserViewSet):
    index_view_class = UserIndexView
    add_view_class = UserCreateView
    edit_view_class = UserEditView
    delete_view_class = UserDeleteView
    # The viewset hands its template to the view, overriding the view's own.
    edit_template_name = "accounts/admin/user_edit.html"

    def get_form_class(self, for_update=False):
        return SiteUserEditForm


class SiteGroupViewSet(GroupViewSet):
    menu_label = "用户组"
