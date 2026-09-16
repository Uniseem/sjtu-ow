from django import forms
from django.utils.translation import gettext_lazy as _
from wagtail.admin.forms import WagtailAdminModelForm

from core.crypto import encrypt_value
from core.models import SiteSettings


class SiteSettingsAdminForm(WagtailAdminModelForm):
    """Hide the stored SMTP ciphertext; blank means keep the current secret."""

    smtp_password = forms.CharField(
        label=_("SMTP 密码"),
        required=False,
        widget=forms.PasswordInput(
            render_value=False,
            attrs={"autocomplete": "new-password"},
        ),
        help_text="加密存储。留空表示不修改已保存的密码。",
    )

    def save(self, commit=True):
        raw = (self.cleaned_data.get("smtp_password") or "").strip()
        instance = super().save(commit=False)
        if raw:
            instance.smtp_password = encrypt_value(raw)
        elif instance.pk:
            instance.smtp_password = (
                SiteSettings.objects.filter(pk=instance.pk)
                .values_list("smtp_password", flat=True)
                .first()
                or ""
            )
        if commit:
            instance.save()
            self.save_m2m()
        return instance
