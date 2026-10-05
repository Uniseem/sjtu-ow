import re

from django import forms
from django.core.exceptions import ValidationError
from django.core.validators import MaxLengthValidator, MinLengthValidator

from accounts.models import (
    BATTLTAG_TAKEN,
    ContactMethod,
    GameAccount,
    User,
    validate_battletag,
)
from accounts.ranks import parse_rank_choice, rank_select_choices
from accounts.roles import ROLE_CHOICES, join_roles, parse_roles
from accounts.services import add_contact_method, add_game_account, max_game_accounts


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


LINK_IN_TEXT = re.compile(r"https?:|www\.|\.(?:com|cn|net|org|top|xyz)\b", re.I)


class ProfileForm(forms.ModelForm):
    is_sjtu = forms.TypedChoiceField(
        label="是否来自上海交通大学",
        choices=(("true", "是"), ("false", "否")),
        coerce=_as_bool,
        widget=forms.RadioSelect,
    )
    # Public on the member page and team pages (design-details 3, v5.2).
    main_role = forms.ChoiceField(
        label="主位置",
        choices=[("", "不填"), *ROLE_CHOICES],
        required=False,
        widget=forms.RadioSelect,
    )
    flex_roles = forms.MultipleChoiceField(
        label="也能打",
        choices=ROLE_CHOICES,
        required=False,
        widget=forms.CheckboxSelectMultiple,
        help_text="主位置以外还能打的位置。三个都选显示为「全能」。",
    )

    class Meta:
        model = User
        fields = [
            "nickname",
            "is_sjtu",
            "motto",
            "main_role",
            "flex_roles",
            "show_rank",
        ]
        labels = {"show_rank": "在成员展示和战队主页公开我的段位"}
        help_texts = {
            "motto": "一句话，最多 30 字，所有人都看得到；不能放链接。",
            "show_rank": (
                "公开的是每个位置在你所有游戏 ID 里最高的段位，游戏 ID 本身不公开。"
            ),
        }
        widgets = {
            "nickname": forms.TextInput(attrs={"autocomplete": "nickname"}),
            "motto": forms.TextInput(attrs={"maxlength": 30}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["nickname"].validators = [
            MinLengthValidator(2),
            MaxLengthValidator(16),
        ]
        self.fields["nickname"].min_length = 2
        self.fields["nickname"].max_length = 16
        if self.instance.pk:
            self.initial["is_sjtu"] = "true" if self.instance.is_sjtu else "false"
            self.initial["flex_roles"] = parse_roles(self.instance.flex_roles)

    def clean_nickname(self) -> str:
        return self.cleaned_data["nickname"].strip()

    def clean_motto(self) -> str:
        """One line, no links (design-details 3.1)."""
        motto = " ".join((self.cleaned_data.get("motto") or "").split())
        if LINK_IN_TEXT.search(motto):
            raise ValidationError("个人宣言里不能放链接。")
        return motto

    def clean_flex_roles(self) -> str:
        return join_roles(self.cleaned_data.get("flex_roles") or [])

    def clean(self):
        cleaned = super().clean()
        main = cleaned.get("main_role") or ""
        flex = [
            role for role in parse_roles(cleaned.get("flex_roles", "")) if role != main
        ]
        cleaned["flex_roles"] = join_roles(flex)
        return cleaned


class RankChoiceField(forms.TypedChoiceField):
    def __init__(self, **kwargs):
        kwargs.setdefault("choices", rank_select_choices())
        kwargs.setdefault("coerce", parse_rank_choice)
        kwargs.setdefault("empty_value", None)
        kwargs.setdefault("required", False)
        super().__init__(**kwargs)


class GameAccountForm(forms.ModelForm):
    rank_tank = RankChoiceField(label="坦克段位")
    rank_damage = RankChoiceField(label="输出段位")
    rank_support = RankChoiceField(label="支援段位")

    class Meta:
        model = GameAccount
        fields = ["battletag", "rank_tank", "rank_damage", "rank_support"]
        widgets = {
            "battletag": forms.TextInput(
                attrs={
                    "autocomplete": "off",
                    "spellcheck": "false",
                    "placeholder": "名称#12345",
                    "class": "font-code",
                }
            ),
        }

    def __init__(self, *args, user=None, **kwargs):
        self.user = user
        super().__init__(*args, **kwargs)
        self.fields["battletag"].label = "游戏 ID"

    def clean_battletag(self) -> str:
        tag = self.cleaned_data["battletag"].strip()
        validate_battletag(tag)
        qs = GameAccount.objects.filter(battletag__iexact=tag)
        if self.instance.pk:
            qs = qs.exclude(pk=self.instance.pk)
        if qs.exists():
            raise ValidationError(BATTLTAG_TAKEN)
        return tag

    def save(self, commit=True):
        account = super().save(commit=False)
        if self.user is not None:
            account.user = self.user
        if commit:
            if account.pk:
                account.full_clean()
                account.save()
            else:
                account = add_game_account(
                    account.user,
                    battletag=account.battletag,
                    rank_tank=account.rank_tank,
                    rank_damage=account.rank_damage,
                    rank_support=account.rank_support,
                )
        return account


class ContactMethodForm(forms.ModelForm):
    # The value is checked against its type (design 3.5).
    autosave_together = ("type", "value")

    class Meta:
        model = ContactMethod
        fields = ["type", "value"]

    def __init__(self, *args, user=None, **kwargs):
        self.user = user
        super().__init__(*args, **kwargs)
        self.fields["type"].label = "类型"
        self.fields["value"].label = "内容"

    def save(self, commit=True):
        contact = super().save(commit=False)
        if self.user is not None:
            contact.user = self.user
        if commit:
            if contact.pk:
                contact.full_clean()
                contact.save()
            else:
                contact = add_contact_method(
                    contact.user,
                    type=contact.type,
                    value=contact.value,
                )
        return contact


def game_account_limit_reached(user) -> bool:
    return user.game_accounts.count() >= max_game_accounts()


class DeleteAccountForm(forms.Form):
    """Design 3.8: deleting needs the current password."""

    password = forms.CharField(
        label="当前密码",
        strip=False,
        widget=forms.PasswordInput(attrs={"autocomplete": "current-password"}),
    )

    def __init__(self, *args, user=None, **kwargs):
        self.user = user
        super().__init__(*args, **kwargs)

    def clean_password(self) -> str:
        password = self.cleaned_data["password"]
        if not self.user.check_password(password):
            raise forms.ValidationError("密码不对。")
        return password


class AvatarForm(forms.Form):
    """Pick a picture for your face (design-details 2.3, v6.11). The checks
    here are the cheap ones; the picture itself is checked when it is opened
    (accounts.images)."""

    file = forms.FileField(
        label="上传新头像",
        help_text=(
            "JPG、PNG 或 WebP，不超过 5MB，至少 128×128 像素。会从中间裁成正方形，"
            "想要别的范围请先自己裁好。选好图片就上传，马上换上。"
        ),
        widget=forms.FileInput(attrs={"accept": "image/jpeg,image/png,image/webp"}),
        # Not marked as required (round 203): choosing a picture is the
        # upload itself, not a box to fill before saving something else.
        required=False,
    )

    def clean_file(self):
        from accounts.images import AVATAR_EXTENSIONS, AVATAR_MAX_BYTES, AVATAR_TYPES

        uploaded = self.cleaned_data.get("file")
        if not uploaded:
            raise ValidationError("先选一张图片。")
        if uploaded.size > AVATAR_MAX_BYTES:
            raise ValidationError("头像不能超过 5MB。")
        name = (uploaded.name or "").lower()
        content_type = getattr(uploaded, "content_type", "")
        if not name.endswith(AVATAR_EXTENSIONS) or (
            content_type and content_type not in AVATAR_TYPES
        ):
            raise ValidationError("头像只支持 JPG、PNG 或 WebP。")
        return uploaded
