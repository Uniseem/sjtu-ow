from django import forms
from django.utils.translation import gettext_lazy as _
from wagtail.admin.forms import WagtailAdminModelForm

# Stored secrets the form never shows again: blank keeps the saved value.
SECRET_FIELDS = {
    "smtp_password": (_("SMTP 密码"), "加密存储。留空表示不修改已保存的密码。"),
    # Round 115: it used to show decrypted in a plain text box.
    "backup_s3_secret_access_key": (
        "密钥（Secret Access Key）",
        "加密存储。留空表示不修改已保存的密钥。",
    ),
}


def _secret_field(label, help_text):
    return forms.CharField(
        label=label,
        required=False,
        widget=forms.PasswordInput(
            render_value=False,
            attrs={"autocomplete": "new-password"},
        ),
        help_text=help_text,
    )


class SiteSettingsAdminForm(WagtailAdminModelForm):
    """Hide the stored secrets; blank means keep the current one."""

    smtp_password = _secret_field(*SECRET_FIELDS["smtp_password"])
    backup_s3_secret_access_key = _secret_field(
        *SECRET_FIELDS["backup_s3_secret_access_key"]
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for name in SECRET_FIELDS:
            if name in self.fields:
                self.fields[name].initial = ""
                self.initial[name] = ""

    def _kept(self, name):
        raw = (self.cleaned_data.get(name) or "").strip()
        if raw:
            return raw
        if self.instance.pk:
            return getattr(self.instance, name)
        return ""

    def clean_smtp_password(self):
        return self._kept("smtp_password")

    def clean_backup_s3_secret_access_key(self):
        return self._kept("backup_s3_secret_access_key")
