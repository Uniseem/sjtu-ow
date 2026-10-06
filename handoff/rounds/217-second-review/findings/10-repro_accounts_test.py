"""217 复核 10（账号）的复现脚本。只读复现，不改业务代码。

在测试机上跑：
  bash scripts/remote-check.sh run uv run pytest -q -s -p no:cacheprovider \
      handoff/rounds/217-second-review/findings/10-repro_accounts_test.py

断言写的是「现在的（有缺陷的）行为」，所以绿 = 缺陷复现了；-s 把看到的东西打印出来。
全部是普通 django_db 测试（不用 transaction=True，免得清空 --reuse-db 的测试库）；
会出异常的请求包在 transaction.atomic() 里，让测试的外层事务还能继续用。
"""

from __future__ import annotations

import pytest
from allauth.account.models import EmailAddress
from django.contrib.auth.models import Group
from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction
from django.test import Client
from django.urls import reverse
from django.utils import timezone

from accounts.models import (
    ContactType,
    Feature,
    FeatureGroupRestriction,
    User,
    validate_contact_value,
)
from accounts.services import GROUP_SUBMITTER, add_game_account

PASSWORD = "Correct-Horse-Battery-1"


def _user(email, nickname, *, verified=True, **extra):
    user = User.objects.create_user(
        email=email,
        password=PASSWORD,
        nickname=nickname,
        agreed_terms_at=timezone.now(),
        agreed_cross_border_at=timezone.now(),
        **extra,
    )
    EmailAddress.objects.create(
        user=user, email=email, verified=verified, primary=True
    )
    return user


def _attempt(call):
    """Run one request; return the exception it raised (or None) and keep the
    test's own transaction usable."""
    try:
        with transaction.atomic():
            call()
    except Exception as exc:  # noqa: BLE001
        return exc
    return None


# --- 10-1: 对「投稿者」组关掉「投稿」→ 信号无限递归 ------------------------------


@pytest.mark.django_db
def test_restricting_article_submit_for_the_submitter_group_recurses():
    admin = _user("su@repro.test", "超管", is_staff=True, is_superuser=True)
    member = _user("m@repro.test", "成员")
    group = Group.objects.get(name=GROUP_SUBMITTER)
    assert member.groups.filter(pk=group.pk).exists()
    print("\n成员验证过邮箱，在「投稿者」组里：", True)

    client = Client()
    client.force_login(admin)
    url = reverse("backoffice:role_restriction_add", args=[group.pk])
    error = _attempt(
        lambda: client.post(url, {"feature": Feature.ARTICLE_SUBMIT, "note": "暂停"})
    )
    print("后台「角色」页对投稿者组关掉投稿：", type(error).__name__, str(error)[:80])
    assert isinstance(error, RecursionError)

    # 线上没有包住整次请求的事务：限制那一行在信号之前已经自动提交了。这里不带
    # 信号地写进去，看之后会怎样。
    FeatureGroupRestriction.objects.bulk_create(
        [FeatureGroupRestriction(group=group, feature=Feature.ARTICLE_SUBMIT)]
    )
    visitor = Client()
    error = _attempt(
        lambda: visitor.post(
            reverse("account_login"), {"login": "m@repro.test", "password": PASSWORD}
        )
    )
    print("之后任何验证过邮箱的成员登录：", type(error).__name__)
    assert isinstance(error, RecursionError)

    # 对照：关掉别的组的投稿不会这样
    other = Group.objects.create(name="观察名单")
    member.groups.add(other)
    FeatureGroupRestriction.objects.filter(group=group).delete()
    error = _attempt(
        lambda: FeatureGroupRestriction.objects.create(
            group=other, feature=Feature.ARTICLE_SUBMIT
        )
    )
    print("对照：关掉自建组的投稿：", type(error).__name__ if error else "正常")
    assert error is None


# --- 10-2: 改邮箱改成一个「没验证的账号」占着的地址 → 500 -------------------------


@pytest.mark.django_db
def test_changing_email_to_an_address_an_unverified_account_holds():
    _user("taken@repro.test", "没验证的", verified=False)
    _user("me@repro.test", "我")
    client = Client()
    response = client.post(
        reverse("account_login"), {"login": "me@repro.test", "password": PASSWORD}
    )
    assert response.status_code == 302
    response = client.post(
        reverse("account_email"), {"action_add": "", "email": "taken@repro.test"}
    )
    print("\n加新邮箱 taken@repro.test：", response.status_code, response.get("Location"))
    code = client.session["account_email_verification_code"]["code"]
    error = _attempt(
        lambda: client.post(reverse("account_email_verification_sent"), {"code": code})
    )
    print("输入发到新邮箱的验证码：", type(error).__name__, str(error)[:100])
    assert isinstance(error, IntegrityError)


# --- 10-3: 游戏 ID 的「不区分大小写唯一」只管 ASCII；全角数字也算数字 ----------------


@pytest.mark.django_db
def test_battletag_uniqueness_is_ascii_only_and_digits_are_unicode():
    one = _user("a@repro.test", "甲")
    two = _user("b@repro.test", "乙")
    three = _user("c@repro.test", "丙")
    add_game_account(one, battletag="Émile#1234")
    add_game_account(two, battletag="émile#1234")
    add_game_account(three, battletag="Émile#１２３４")
    tags = sorted(
        account.battletag
        for account in one.game_accounts.all()
        | two.game_accounts.all()
        | three.game_accounts.all()
    )
    print("\n三个账号各自绑上了：", tags)
    assert len(tags) == 3

    for kind, value in (
        (ContactType.QQ, "１２３４５６"),
        (ContactType.PHONE, "1３８００１３８０００"),
        (ContactType.QQ, "¹²³⁴⁵"),
    ):
        try:
            validate_contact_value(kind, value)
            outcome = "通过"
        except ValidationError:
            outcome = "被拒"
        print(f"联系方式 {kind} {value!r}：{outcome}")
        assert outcome == "通过"
