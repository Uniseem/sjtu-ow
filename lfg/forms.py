"""LFG forms (design 6.1)."""

from __future__ import annotations

from django import forms
from django.utils import timezone

from accounts.models import GameAccount
from core.models import GameMode
from lfg.models import LfgPost


class LfgPostForm(forms.ModelForm):
    role_tank = forms.BooleanField(label="缺重装", required=False)
    role_damage = forms.BooleanField(label="缺输出", required=False)
    role_support = forms.BooleanField(label="缺支援", required=False)

    class Meta:
        model = LfgPost
        fields = ["game_account", "mode", "start_at", "note"]
        widgets = {
            "start_at": forms.DateTimeInput(
                attrs={"type": "datetime-local"}, format="%Y-%m-%dT%H:%M"
            ),
            "note": forms.Textarea(attrs={"rows": 3, "maxlength": 200}),
        }

    def __init__(self, *args, user=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.user = user
        self.fields["game_account"].queryset = GameAccount.objects.filter(user=user)
        self.fields["game_account"].label = "游戏 ID"
        self.fields["game_account"].help_text = "会公开显示在车帖上。"
        self.fields["mode"].queryset = GameMode.objects.filter(is_active=True)
        self.fields["note"].required = False
        self.fields["start_at"].input_formats = ["%Y-%m-%dT%H:%M", "%Y-%m-%d %H:%M"]
        if not self.instance.pk:
            self.fields["start_at"].initial = timezone.localtime().strftime(
                "%Y-%m-%dT%H:%M"
            )

    def clean(self):
        cleaned = super().clean()
        if not any(
            cleaned.get(name) for name in ("role_tank", "role_damage", "role_support")
        ):
            raise forms.ValidationError("请至少选择一个缺的位置。")
        return cleaned

    def roles(self) -> dict:
        return {
            "tank": self.cleaned_data.get("role_tank", False),
            "damage": self.cleaned_data.get("role_damage", False),
            "support": self.cleaned_data.get("role_support", False),
        }
