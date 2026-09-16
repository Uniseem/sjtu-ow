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


class ProfileForm(forms.ModelForm):
    is_sjtu = forms.TypedChoiceField(
        label="是否来自上海交通大学",
        choices=(("true", "是"), ("false", "否")),
        coerce=_as_bool,
        widget=forms.RadioSelect,
    )

    class Meta:
        model = User
        fields = ["nickname", "is_sjtu"]
        widgets = {
            "nickname": forms.TextInput(attrs={"autocomplete": "nickname"}),
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

    def clean_nickname(self) -> str:
        return self.cleaned_data["nickname"].strip()


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
