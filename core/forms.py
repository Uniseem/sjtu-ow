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
    # v7.1: AI review's key moved here from the environment (design 5.5.3).
    "moderation_api_key": (
        "接口密钥",
        "服务商给的 API Key，加密存储。留空表示不修改已保存的密钥。",
    ),
}


def kept_secret(form, name):
    """A secret box left blank keeps what is stored."""
    raw = (form.cleaned_data.get(name) or "").strip()
    if raw:
        return raw
    return getattr(form.instance, name) if form.instance.pk else ""


def cleaned_extra_body(form):
    from moderation.services import clean_extra_body

    try:
        return clean_extra_body(form.cleaned_data.get("moderation_extra_body"))
    except ValueError as exc:
        raise forms.ValidationError(str(exc)) from exc


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
    moderation_api_key = _secret_field(*SECRET_FIELDS["moderation_api_key"])

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for name in SECRET_FIELDS:
            if name in self.fields:
                self.fields[name].initial = ""
                self.initial[name] = ""

    def clean_smtp_password(self):
        return kept_secret(self, "smtp_password")

    def clean_backup_s3_secret_access_key(self):
        return kept_secret(self, "backup_s3_secret_access_key")

    def clean_moderation_api_key(self):
        return kept_secret(self, "moderation_api_key")

    def clean_moderation_extra_body(self):
        return cleaned_extra_body(self)
