"""Team forms (design 7.1, 7.3)."""

from __future__ import annotations

from django import forms
from django.core.validators import MaxLengthValidator, MinLengthValidator

from accounts.roles import ROLE_CHOICES, join_roles, parse_roles
from teams.models import Team

LOGO_MAX_BYTES = 5 * 1024 * 1024
LOGO_TYPES = {"image/jpeg", "image/png", "image/webp"}
LOGO_EXTENSIONS = (".jpg", ".jpeg", ".png", ".webp")


class TeamForm(forms.ModelForm):
    logo_file = forms.ImageField(
        label="队标",
        required=False,
        help_text="JPG、PNG 或 WebP，不超过 5MB，显示时裁剪为正方形。",
    )
    remove_logo = forms.BooleanField(label="删除队标", required=False)
    # Shown with 「招募中」 (design-details 5.2, v5.2).
    recruiting_roles = forms.MultipleChoiceField(
        label="缺的位置",
        choices=ROLE_CHOICES,
        required=False,
        widget=forms.CheckboxSelectMultiple,
        help_text="招募中时显示在战队卡和战队主页上。都不勾表示哪个位置都要。",
    )

    class Meta:
        model = Team
        fields = ["name", "description", "is_recruiting", "recruiting_roles"]
        widgets = {
            "description": forms.Textarea(attrs={"rows": 4, "maxlength": 500}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["name"].validators = [MinLengthValidator(2), MaxLengthValidator(16)]
        self.fields["name"].help_text = "2 到 16 个字符，不能和现有战队重名。"
        self.fields["description"].required = False
        if self.instance.pk:
            self.initial["recruiting_roles"] = parse_roles(
                self.instance.recruiting_roles
            )
        if not self.instance.pk:
            # Nothing to remove yet on the create form.
            self.fields.pop("remove_logo", None)

    def clean_recruiting_roles(self) -> str:
        return join_roles(self.cleaned_data.get("recruiting_roles") or [])

    def clean_name(self):
        return (self.cleaned_data["name"] or "").strip()

    def clean_logo_file(self):
        uploaded = self.cleaned_data.get("logo_file")
        if not uploaded:
            return uploaded
        if uploaded.size > LOGO_MAX_BYTES:
            raise forms.ValidationError("队标不能超过 5MB。")
        name = (uploaded.name or "").lower()
        content_type = getattr(uploaded, "content_type", "")
        if not name.endswith(LOGO_EXTENSIONS) or (
            content_type and content_type not in LOGO_TYPES
        ):
            raise forms.ValidationError("队标只支持 JPG、PNG 或 WebP。")
        return uploaded


class ApplicationForm(forms.Form):
    role_tank = forms.BooleanField(label="坦克", required=False)
    role_damage = forms.BooleanField(label="输出", required=False)
    role_support = forms.BooleanField(label="支援", required=False)
    message = forms.CharField(
        label="留言",
        required=False,
        max_length=200,
        widget=forms.Textarea(attrs={"rows": 3, "maxlength": 200}),
        help_text="最多 200 字。提交申请后，队长可以看到你的游戏 ID 和段位。",
    )

    def clean(self):
        cleaned = super().clean()
        if not any(
            cleaned.get(name) for name in ("role_tank", "role_damage", "role_support")
        ):
            raise forms.ValidationError("请至少选择一个意向位置。")
        return cleaned

    def roles(self) -> dict:
        return {
            "tank": self.cleaned_data.get("role_tank", False),
            "damage": self.cleaned_data.get("role_damage", False),
            "support": self.cleaned_data.get("role_support", False),
        }


class RejectForm(forms.Form):
    note = forms.CharField(label="拒绝原因", required=False, max_length=200)
