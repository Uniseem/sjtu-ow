from django import forms
from django.utils.translation import gettext_lazy as _
from wagtail.admin.forms import WagtailAdminModelForm


class SiteSettingsAdminForm(WagtailAdminModelForm):
    """Hide the stored SMTP secret; blank means keep the current password."""

    smtp_password = forms.CharField(
        label=_("SMTP 密码"),
        required=False,
        widget=forms.PasswordInput(
            render_value=False,
            attrs={"autocomplete": "new-password"},
        ),
        help_text="加密存储。留空表示不修改已保存的密码。",
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["smtp_password"].initial = ""
        self.initial["smtp_password"] = ""

    def clean_smtp_password(self):
        raw = (self.cleaned_data.get("smtp_password") or "").strip()
        if raw:
            return raw
        if self.instance.pk:
            return self.instance.smtp_password
        return ""
