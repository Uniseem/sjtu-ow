"""Chinese labels for django-allauth forms (ACCOUNT_FORMS)."""

from allauth.account import forms as allauth_forms


def _relabel(form, labels: dict[str, str]) -> None:
    for name, label in labels.items():
        field = form.fields.get(name)
        if field is None:
            continue
        field.label = label
        if field.widget.attrs.get("placeholder"):
            field.widget.attrs["placeholder"] = label


class LoginForm(allauth_forms.LoginForm):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        _relabel(self, {"login": "邮箱", "password": "密码"})
        if "password" in self.fields:
            self.fields["password"].help_text = ""


class SignupForm(allauth_forms.SignupForm):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        _relabel(self, {"email": "邮箱", "password1": "密码", "password2": "确认密码"})


class AddEmailForm(allauth_forms.AddEmailForm):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        _relabel(self, {"email": "邮箱"})


class ChangeEmailForm(allauth_forms.ChangeEmailForm):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        _relabel(self, {"email": "新邮箱"})


class ChangePasswordForm(allauth_forms.ChangePasswordForm):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        _relabel(
            self,
            {
                "oldpassword": "当前密码",
                "password1": "新密码",
                "password2": "确认新密码",
            },
        )


class SetPasswordForm(allauth_forms.SetPasswordForm):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        _relabel(self, {"password1": "新密码", "password2": "确认新密码"})


class ResetPasswordForm(allauth_forms.ResetPasswordForm):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        _relabel(self, {"email": "邮箱"})


class ResetPasswordKeyForm(allauth_forms.ResetPasswordKeyForm):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        _relabel(self, {"password1": "新密码", "password2": "确认新密码"})


class ReauthenticateForm(allauth_forms.ReauthenticateForm):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        _relabel(self, {"password": "密码"})


class ConfirmEmailVerificationCodeForm(allauth_forms.ConfirmEmailVerificationCodeForm):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        _relabel(self, {"code": "验证码"})


class ConfirmPasswordResetCodeForm(allauth_forms.ConfirmPasswordResetCodeForm):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        _relabel(self, {"code": "验证码"})
