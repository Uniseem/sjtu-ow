from django import forms
from django.core.validators import MaxLengthValidator, MinLengthValidator


def _as_bool(value):
    if isinstance(value, bool):
        return value
    return str(value).lower() in {"true", "1", "yes", "on"}


class SignupExtraForm(forms.Form):
    """Extra allauth signup fields (ACCOUNT_SIGNUP_FORM_CLASS)."""

    nickname = forms.CharField(
        label="昵称",
        min_length=2,
        max_length=16,
        validators=[MinLengthValidator(2), MaxLengthValidator(16)],
        widget=forms.TextInput(attrs={"autocomplete": "nickname"}),
    )
    is_sjtu = forms.TypedChoiceField(
        label="是否来自上海交通大学",
        choices=(("true", "是"), ("false", "否")),
        coerce=_as_bool,
        widget=forms.RadioSelect,
    )
    agreed_terms = forms.BooleanField(
        label="我已阅读并同意用户协议和隐私政策",
        required=True,
    )
    agreed_cross_border = forms.BooleanField(
        label="我同意将个人信息存储在境外服务器",
        required=True,
    )

    field_order = [
        "email",
        "nickname",
        "password1",
        "password2",
        "is_sjtu",
        "agreed_terms",
        "agreed_cross_border",
    ]

    def clean_nickname(self) -> str:
        return self.cleaned_data["nickname"].strip()

    def signup(self, request, user) -> None:
        # Fields are stored in AccountAdapter.save_user; groups sync on post_save.
        return None
