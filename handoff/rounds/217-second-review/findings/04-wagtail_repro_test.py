"""217 复核 04（Wagtail 超管路径）的复现脚本。只记录，不修。

每条测试断言的是「现在的缺陷行为」：测试通过 = 缺陷复现。
在测试机上跑：
  bash scripts/remote-check.sh run uv run pytest -q -s \
    handoff/rounds/217-second-review/findings/04-wagtail_repro_test.py
"""

import pytest
from allauth.account.models import EmailAddress
from django.contrib.auth.models import Group
from django.core.management import call_command
from django.test import Client
from django.urls import reverse
from django.utils import timezone

from accounts import services as account_services
from accounts.models import Feature, FeatureGroupRestriction, User
from accounts.permissions import can_use

PW = "Correct-Horse-Battery-1"


def _member(email, *, verified, is_sjtu=False):
    now = timezone.now()
    user = User.objects.create_user(
        email=email,
        password=PW,
        nickname="复核成员",
        is_sjtu=is_sjtu,
        agreed_terms_at=now,
        agreed_cross_border_at=now,
    )
    EmailAddress.objects.create(user=user, email=email, verified=verified, primary=True)
    return user


def _root():
    return User.objects.create_superuser(email="root@example.com", password=PW)


def _logged_in_as(client):
    return client.session.get("_auth_user_id")


# --- 04-1 两个不走 allauth 的登录口 ---------------------------------------------


@pytest.mark.django_db
@pytest.mark.parametrize("path", ["/wagtail/login/", "/_util/login/"])
def test_unverified_account_signs_in_through_the_other_door(path):
    call_command("init_site", verbosity=0)
    user = _member("unverified@example.com", verified=False)

    front = Client()
    r = front.post("/accounts/login/", {"login": user.email, "password": PW})
    print(f"\n[allauth] POST /accounts/login/ -> {r.status_code} {r.get('Location')}"
          f" 登录了吗={_logged_in_as(front)}")
    assert _logged_in_as(front) is None  # 正门：要先验证邮箱

    side = Client(enforce_csrf_checks=False)
    print(f"[{path}] 匿名 GET -> {side.get(path).status_code}")
    r = side.post(path, {"username": user.email, "password": PW})
    print(f"[{path}] POST -> {r.status_code} {r.get('Location')}"
          f" 登录了吗={_logged_in_as(side)}")
    assert _logged_in_as(side) == str(user.pk)  # 侧门：没验证也登进去了
    me = side.get("/me/")
    print(f"[{path}] 之后 GET /me/ -> {me.status_code} {me.get('Location')}")
    print(f"[{path}] can_use(报名内战)={can_use(user, Feature.SCRIM_SIGNUP)}"
          f" can_use(评论)={can_use(user, Feature.ARTICLE_COMMENT)}")


@pytest.mark.django_db
@pytest.mark.parametrize("path", ["/wagtail/login/", "/_util/login/"])
def test_the_other_door_has_no_failed_login_limit(path):
    call_command("init_site", verbosity=0)
    user = _member("victim@example.com", verified=True)

    front = Client()
    codes = [
        front.post("/accounts/login/", {"login": user.email, "password": "wrong"})
        .status_code
        for _ in range(8)
    ]
    r = front.post("/accounts/login/", {"login": user.email, "password": PW})
    print(f"\n[allauth] 8 次错密码 -> {codes}；再用对的密码 -> {r.status_code}"
          f" 登录了吗={_logged_in_as(front)}")

    side = Client()
    codes = [
        side.post(path, {"username": user.email, "password": f"wrong-{i}"})
        .status_code
        for i in range(60)
    ]
    r = side.post(path, {"username": user.email, "password": PW})
    print(f"[{path}] 60 次错密码 状态码集合={sorted(set(codes))}；"
          f"第 61 次对的密码 -> {r.status_code} 登录了吗={_logged_in_as(side)}")
    assert set(codes) == {200}  # 一次都没被限
    assert _logged_in_as(side) == str(user.pk)


# --- 04-2 底层后台的用户编辑页能把注销的账号救活、提成超管 -------------------------


@pytest.mark.django_db
def test_wagtail_user_edit_revives_a_deleted_account(client):
    call_command("init_site", verbosity=0)
    root = _root()
    person = _member("gone@example.com", verified=True)
    account_services.delete_account(person)
    person.refresh_from_db()
    assert account_services.is_deleted(person) and not person.is_active

    # 新后台的「启用」拒绝（213 A8）
    try:
        account_services.reactivate_account(person)
        refused = False
    except account_services.AccountError as exc:
        refused = str(exc)
    print(f"\n[service] reactivate_account -> {refused!r}")

    client.force_login(root)
    url = reverse("wagtailusers_users:edit", args=[person.pk])
    print(f"[wagtail] GET {url} -> {client.get(url).status_code}")
    r = client.post(
        url,
        {
            "email": person.email,
            "nickname": person.nickname,
            "is_active": "on",
            "is_superuser": "on",
            "deactivation_note": person.deactivation_note,
            "password1": "Brand-New-Pass-77",
            "password2": "Brand-New-Pass-77",
        },
    )
    person.refresh_from_db()
    print(f"[wagtail] POST -> {r.status_code} {r.get('Location')}")
    print(f"[wagtail] is_deleted={account_services.is_deleted(person)}"
          f" is_active={person.is_active} is_superuser={person.is_superuser}"
          f" 新密码可用={person.check_password('Brand-New-Pass-77')}"
          f" can_use(报名内战)={can_use(person, Feature.SCRIM_SIGNUP)}")
    assert account_services.is_deleted(person)
    assert person.is_active and person.is_superuser
    assert person.check_password("Brand-New-Pass-77")


@pytest.mark.django_db
def test_wagtail_reactivation_keeps_the_spent_reason(client):
    call_command("init_site", verbosity=0)
    root = _root()
    person = _member("stopped@example.com", verified=True)
    account_services.deactivate_account(person, note="刷屏")
    client.force_login(root)
    url = reverse("wagtailusers_users:edit", args=[person.pk])
    client.post(
        url,
        {
            "email": person.email,
            "nickname": person.nickname,
            "is_active": "on",
            "deactivation_note": "刷屏",  # 表单原样带着
        },
    )
    person.refresh_from_db()
    print(f"\n[wagtail] 重新启用后 is_active={person.is_active}"
          f" deactivation_note={person.deactivation_note!r}")
    assert person.is_active and person.deactivation_note == "刷屏"


# --- 04-3 底层后台改「是否来自交大」，组被表单里的旧勾选盖回去 ----------------------


@pytest.mark.django_db
def test_wagtail_is_sjtu_change_leaves_the_old_group(client):
    call_command("init_site", verbosity=0)
    root = _root()
    person = _member("ext@example.com", verified=True, is_sjtu=False)
    external = Group.objects.get(name=account_services.GROUP_EXTERNAL)
    FeatureGroupRestriction.objects.create(
        group=external, feature=Feature.TOURNAMENT_REGISTER, note="校外不开"
    )
    shown = list(person.groups.values_list("pk", flat=True))  # 页面上勾着的
    print(f"\n改之前：is_sjtu={person.is_sjtu}"
          f" 组={sorted(person.groups.values_list('name', flat=True))}")

    client.force_login(root)
    url = reverse("wagtailusers_users:edit", args=[person.pk])
    r = client.post(
        url,
        {
            "email": person.email,
            "nickname": person.nickname,
            "is_sjtu": "on",
            "is_active": "on",
            "groups": shown,
        },
    )
    person.refresh_from_db()
    names = sorted(person.groups.values_list("name", flat=True))
    print(f"[wagtail] POST -> {r.status_code}；改之后：is_sjtu={person.is_sjtu} 组={names}"
          f" can_use(报名赛事)={can_use(person, Feature.TOURNAMENT_REGISTER)}")
    assert person.is_sjtu
    assert account_services.GROUP_EXTERNAL in names
    assert account_services.GROUP_SJTU not in names
    assert not can_use(person, Feature.TOURNAMENT_REGISTER)


# --- 04-4 底层后台改登录邮箱：不验证、旧地址照样能登录 ------------------------------


@pytest.mark.django_db
def test_wagtail_email_change_skips_verification(client):
    call_command("init_site", verbosity=0)
    root = _root()
    person = _member("old@example.com", verified=True)
    client.force_login(root)
    url = reverse("wagtailusers_users:edit", args=[person.pk])
    r = client.post(
        url,
        {
            "email": "New@Example.com",
            "nickname": person.nickname,
            "is_active": "on",
        },
    )
    person.refresh_from_db()
    rows = list(EmailAddress.objects.filter(user=person).values_list(
        "email", "verified", "primary"))
    print(f"\n[wagtail] POST -> {r.status_code}；user.email={person.email!r}"
          f" EmailAddress={rows}"
          f" email_is_verified={account_services.email_is_verified(person)}")
    old = Client()
    old.post("/accounts/login/", {"login": "old@example.com", "password": PW})
    print(f"[allauth] 用旧地址登录 -> 登录了吗={_logged_in_as(old)}")
    assert person.email == "New@Example.com"
    assert rows == [("old@example.com", True, True)]
    assert _logged_in_as(old) == str(person.pk)


# --- 04-5 底层后台设页面隐私：静态文件留着，Caddy 照发 ------------------------------


@pytest.mark.django_db
def test_wagtail_privacy_leaves_the_static_file(
    client, settings, tmp_path, django_capture_on_commit_callbacks
):
    from content.models import ArticleCategory, ArticleIndexPage, ArticlePage
    from core import prerender

    settings.PRERENDER_ENABLED = True
    settings.PRERENDER_ROOT = tmp_path
    prerender.forget_targets()
    call_command("init_site", verbosity=0)
    root = _root()
    index = ArticleIndexPage.objects.live().first()
    page = ArticlePage(
        title="要设成私密的文章",
        slug="soon-private",
        category=ArticleCategory.objects.first(),
        summary="摘要",
        body="正文",
        owner=root,
    )
    index.add_child(instance=page)
    page.save_revision().publish()
    url = page.get_url()
    prerender.generate(url, kind="article")
    target = prerender.file_for(url)
    assert target.exists()

    client.force_login(root)
    with django_capture_on_commit_callbacks(execute=True) as callbacks:
        r = client.post(
            reverse("wagtailadmin_pages:set_privacy", args=[page.pk]),
            {"restriction_type": "login"},
        )
    anonymous = Client().get(url)
    print(f"\n[wagtail] 设「登录后可见」 -> {r.status_code}；on_commit 回调 {len(callbacks)} 个")
    print(f"匿名访问 Django -> {anonymous.status_code} {anonymous.get('Location')}")
    print(f"静态文件还在={target.exists()}  在全量目标里={url in prerender.page_targets()}")
    assert anonymous.status_code == 302
    assert target.exists()
    assert url not in prerender.page_targets()
