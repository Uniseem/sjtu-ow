from allauth.account.adapter import DefaultAccountAdapter
from django.utils import timezone
from django.utils.encoding import force_str

from core.mail import get_from_email


def user_display(user) -> str:
    nickname = getattr(user, "nickname", "") or ""
    return nickname or getattr(user, "email", "") or str(user)


class AccountAdapter(DefaultAccountAdapter):
    """Email-login adapter: extra signup fields and SiteSettings From header."""

    error_messages = {
        **DefaultAccountAdapter.error_messages,
        "account_inactive": "这个账号目前已被停用。",
        "cannot_remove_primary_email": "不能删除当前登录邮箱。",
        "duplicate_email": "这个邮箱已经绑定在当前账号上。",
        "email_password_mismatch": "邮箱或密码不正确。",
        "email_taken": "这个邮箱已经注册过。",
        "enter_current_password": "请输入当前密码。",
        "incorrect_code": "验证码不正确。",
        "incorrect_password": "密码不正确。",
        "invalid_or_expired_key": "链接无效或已过期。",
        "invalid_login": "登录信息不正确。",
        "invalid_password_reset": "找回密码凭证无效。",
        "max_email_addresses": "最多只能添加 %d 个邮箱。",
        "too_many_login_attempts": "登录失败次数过多，请稍后再试。",
        "unknown_email": "这个邮箱还没有注册。",
        "unverified_primary_email": "请先验证登录邮箱。",
        "username_password_mismatch": "用户名或密码不正确。",
        "select_only_one": "请只选择一项。",
        "same_as_current": "新值必须和当前值不同。",
        "rate_limited": "操作太频繁，请稍后再试。",
    }

    def format_email_subject(self, subject: str) -> str:
        # Prefix is applied once by the mail delivery layer (design 10.1).
        return force_str(subject)

    def get_from_email(self) -> str:
        return get_from_email()

    def save_user(self, request, user, form, commit=True):
        user = super().save_user(request, user, form, commit=False)
        data = form.cleaned_data
        nickname = (data.get("nickname") or "").strip()
        if nickname:
            user.nickname = nickname
        if "is_sjtu" in data:
            user.is_sjtu = bool(data["is_sjtu"])
        now = timezone.now()
        if data.get("agreed_terms"):
            user.agreed_terms_at = now
        if data.get("agreed_cross_border"):
            user.agreed_cross_border_at = now
        if commit:
            user.save()
        return user
