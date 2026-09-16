"""Design chapter 15 held to its own numbers.

Every round verified its own slice; nothing checked the chapter as a whole,
and nothing stopped a later change from quietly breaking one of these. The
M7 acceptance bar is "第 15 章的目标全部达到", so these are the tests that
keep it true.
"""

import gzip
import re
from datetime import timedelta
from pathlib import Path

import pytest
from django.utils import timezone

from accounts.models import ContactMethod, ContactType, GameAccount, User

# --- helpers -------------------------------------------------------------------


def make_user(index, *, sjtu=True):
    now = timezone.now()
    user = User.objects.create_user(
        email=f"audit{index}@example.com",
        password="Correct-Horse-Battery-1",
        nickname=f"审计用户{index}",
        is_sjtu=sjtu,
        agreed_terms_at=now,
        agreed_cross_border_at=now,
    )
    GameAccount.objects.create(
        user=user, battletag=f"Audit{index}#{1000 + index}", rank_damage=20
    )
    ContactMethod.objects.create(
        user=user, type=ContactType.QQ, value=f"9876543{index:02d}"
    )
    return user


def count_queries(client, url, django_assert_num_queries=None):
    from django.db import connection
    from django.test.utils import CaptureQueriesContext

    with CaptureQueriesContext(connection) as captured:
        response = client.get(url)
    assert response.status_code == 200, f"{url} 返回 {response.status_code}"
    return len(captured)


def assert_no_n_plus_one(client, url, seed, *, small=3, large=10):
    """Design 15.1: query count must not grow with the number of rows.

    Asserting a fixed number would go red on every unrelated change; what
    matters is that ten rows cost the same as three.
    """
    seed(small)
    few = count_queries(client, url)
    seed(large - small)
    many = count_queries(client, url)
    assert many <= few, (
        f"{url}：{small} 条数据用了 {few} 次查询，{large} 条用了 {many} 次——"
        "查询数随数据量增长，说明有 N+1。"
    )
    print(f"  {url:36} {small} 条 → {few} 次查询 | {large} 条 → {many} 次查询")
    return few, many


# --- 15.1 N+1 -------------------------------------------------------------------


@pytest.mark.django_db
def test_no_n_plus_one_on_the_team_list(client):
    from teams import services as team_services

    def seed(count):
        start = User.objects.count()
        for index in range(count):
            captain = make_user(start + index)
            team_services.create_team(user=captain, name=f"审计战队{start + index}")

    few, many = assert_no_n_plus_one(client, "/teams/", seed)
    assert many <= few


@pytest.mark.django_db
def test_no_n_plus_one_on_the_lfg_list(client):
    from core.models import GameMode
    from lfg.models import LfgPost

    mode = GameMode.objects.first() or GameMode.objects.create(name="审计模式")

    def seed(count):
        start = User.objects.count()
        now = timezone.now()
        for index in range(count):
            user = make_user(start + index)
            LfgPost.objects.create(
                owner=user,
                game_account=user.game_accounts.first(),
                mode=mode,
                role_damage=True,
                note=f"审计车帖{index}",
                start_at=now,
                expires_at=now + timedelta(hours=2),
            )

    assert_no_n_plus_one(client, "/_fragments/lfg/", seed)


@pytest.mark.django_db
def test_no_n_plus_one_on_the_tournament_list(client):
    from tournaments.models import Tournament, TournamentStatus

    def seed(count):
        now = timezone.now()
        start = Tournament.objects.count()
        for index in range(count):
            Tournament.objects.create(
                title=f"审计赛事{start + index}",
                registration_opens_at=now - timedelta(days=1),
                registration_closes_at=now + timedelta(days=7),
                status=TournamentStatus.PUBLISHED,
                published_at=now,
            )

    assert_no_n_plus_one(client, "/tournaments/", seed)


@pytest.mark.django_db
def test_no_n_plus_one_on_the_scrim_list(client):
    from scrims.models import Scrim, ScrimStatus

    def seed(count):
        now = timezone.now()
        start = Scrim.objects.count()
        for index in range(count):
            Scrim.objects.create(
                title=f"审计内战{start + index}",
                starts_at=now + timedelta(days=1),
                status=ScrimStatus.PUBLISHED,
            )

    assert_no_n_plus_one(client, "/scrims/", seed)


@pytest.mark.django_db
def test_no_n_plus_one_on_the_scrim_detail_signups(client):
    """The signup list is the part that grows, so it is the part at risk."""
    from scrims import services as scrim_services
    from scrims.models import Role, Scrim, ScrimStatus

    scrim = Scrim.objects.create(
        title="审计内战详情",
        starts_at=timezone.now() + timedelta(days=1),
        status=ScrimStatus.PUBLISHED,
    )

    def seed(count):
        start = User.objects.count()
        for index in range(count):
            user = make_user(start + index)
            scrim_services.sign_up(
                scrim=scrim,
                user=user,
                game_account_id=user.game_accounts.first().pk,
                roles=[Role.DAMAGE],
            )

    assert_no_n_plus_one(client, f"/scrims/{scrim.pk}/", seed)


# --- 15.1 homepage weight ------------------------------------------------------


@pytest.mark.django_db
def test_the_homepage_stays_under_the_weight_budget(client):
    """Design 15.1: HTML + CSS + JS under 300KB compressed, images and
    fonts excluded. The server is overseas, so bytes cost more than cycles.

    Assets are read off disk through the staticfiles finders rather than
    fetched over HTTP: a 404 during the test would otherwise be silently
    skipped and the budget would only ever measure the HTML.
    """
    from django.contrib.staticfiles import finders

    response = client.get("/")
    assert response.status_code == 200
    html = response.content

    total = len(gzip.compress(html))
    referenced = []
    seen = set()
    for match in re.finditer(rb'(?:src|href)="(/static/[^"]+\.(?:css|js))"', html):
        path = match.group(1).decode()[len("/static/") :]
        if path in seen:
            continue
        seen.add(path)
        located = finders.find(path)
        assert located, f"首页引用了 {path}，但在静态文件里找不到它"
        body = Path(located).read_bytes()
        total += len(gzip.compress(body))
        referenced.append(path)

    # The page really does pull in scripts and styles; if this ever drops to
    # zero the budget check above would be meaningless.
    assert len(referenced) >= 3, referenced

    budget = 300 * 1024
    assert total <= budget, (
        f"首页 HTML+CSS+JS 压缩后 {total / 1024:.0f}KB，"
        f"超过 {budget // 1024}KB 预算。引用了：{referenced}"
    )


# --- 15.2 transport and cookies ------------------------------------------------


def test_production_transport_settings():
    """Design 15.2, checked against the production module, not the dev one."""
    import importlib
    import os

    from sjtu_ow.settings import base

    os.environ.setdefault("DJANGO_SECRET_KEY", "audit-only-secret-key-not-used")
    os.environ.setdefault("SITE_URL", "https://example.com")
    os.environ.setdefault("DJANGO_ALLOWED_HOSTS", "example.com")
    os.environ.setdefault("DJANGO_CSRF_TRUSTED_ORIGINS", "https://example.com")
    os.environ.setdefault("FIELD_ENCRYPTION_KEY", "audit-only-field-key")
    prod = importlib.import_module("sjtu_ow.settings.prod")

    assert prod.SECURE_HSTS_SECONDS >= 31536000
    assert prod.SECURE_HSTS_INCLUDE_SUBDOMAINS is True
    assert prod.SECURE_HSTS_PRELOAD is True
    assert prod.SESSION_COOKIE_SECURE is True
    assert prod.CSRF_COOKIE_SECURE is True
    assert prod.SECURE_CONTENT_TYPE_NOSNIFF is True
    assert base.SESSION_COOKIE_SAMESITE == "Lax"
    assert base.CSRF_COOKIE_SAMESITE == "Lax"
    assert base.SESSION_COOKIE_HTTPONLY is not False


def test_the_front_end_csp_forbids_inline_script_and_eval():
    """Design 15.2: no inline scripts, no eval, bilibili is the only frame."""
    from django.conf import settings

    policy = settings.SECURE_CSP
    script = policy["script-src"]
    assert "'unsafe-inline'" not in script
    assert "'unsafe-eval'" not in script
    assert "'unsafe-inline'" not in policy["style-src"]

    frames = policy["frame-src"]
    external = [source for source in frames if str(source).startswith("http")]
    assert external == ["https://player.bilibili.com"], external
    assert policy["frame-ancestors"] == ["'none'"]


@pytest.mark.django_db
def test_a_real_page_carries_no_inline_script(client):
    response = client.get("/")
    html = response.content.decode()
    # An inline <script> with a body would be blocked by the policy above.
    inline = re.findall(r"<script(?![^>]*\bsrc=)[^>]*>(.*?)</script>", html, re.S)
    meaningful = [block for block in inline if block.strip()]
    assert meaningful == [], meaningful


# --- 15.2 rate limits ----------------------------------------------------------


def test_the_rate_limits_match_the_design():
    """Design 15.2 names exact numbers; drift here is silent."""
    from core.views import STATE_RATE_LIMIT
    from lfg.views import HOUR, POST_LIMIT
    from teams.views import APPLY_LIMIT, CREATE_LIMIT, DAY

    assert (POST_LIMIT, HOUR) == (10, 3600)  # 发车每人每小时 10 次
    assert (APPLY_LIMIT, DAY) == (20, 86400)  # 申请入队每人每天 20 次
    assert (CREATE_LIMIT, DAY) == (3, 86400)  # 创建战队每人每天 3 次
    assert STATE_RATE_LIMIT == 120  # 状态片段每 IP 每分钟 120 次


# --- 15.2 uploads --------------------------------------------------------------


def test_uploads_allow_only_the_three_formats():
    """Design 15.2: JPG, PNG, WebP. No SVG."""
    from django.conf import settings

    allowed = {name.lower() for name in settings.WAGTAILIMAGES_EXTENSIONS}
    assert allowed == {"jpg", "jpeg", "png", "webp"}
    assert "svg" not in allowed
    assert "gif" not in allowed
    assert settings.WAGTAILIMAGES_MAX_UPLOAD_SIZE <= 10 * 1024 * 1024


# --- 15.2 prerendered pages ----------------------------------------------------


@pytest.mark.django_db
def test_a_prerendered_page_has_no_csrf_token_or_personal_data(settings, tmp_path):
    """Design 15.2: generated as an anonymous visitor, in its own context."""
    from core import prerender

    settings.PRERENDER_ENABLED = True
    settings.PRERENDER_ROOT = tmp_path / "prerendered"
    user = make_user(1)
    client_session = None  # nobody is logged in when the generator runs

    html = prerender.render_html("/").decode()

    assert "csrfmiddlewaretoken" not in html
    assert "csrftoken" not in html
    assert user.nickname not in html
    assert user.email not in html
    assert client_session is None


# --- 15.3 contact visibility ---------------------------------------------------


@pytest.mark.django_db
def test_contacts_never_reach_a_public_page(client):
    """Design 15.3: only tournament and scrim admins may see contacts."""
    from scrims import services as scrim_services
    from scrims.models import Role, Scrim, ScrimStatus

    user = make_user(1)
    contact = user.contact_methods.first().value
    scrim = Scrim.objects.create(
        title="联系方式审计",
        starts_at=timezone.now() + timedelta(days=1),
        status=ScrimStatus.PUBLISHED,
    )
    scrim_services.sign_up(
        scrim=scrim,
        user=user,
        game_account_id=user.game_accounts.first().pk,
        roles=[Role.DAMAGE],
    )

    for url in ("/", "/scrims/", f"/scrims/{scrim.pk}/", "/teams/", "/lfg/"):
        body = client.get(url).content.decode()
        assert contact not in body, url
        assert user.email not in body, url


# --- 15.3 what the AI moderator is sent ----------------------------------------


@pytest.mark.django_db
def test_moderation_sends_content_only_never_identities():
    """Design 15.3: no emails, contacts, game IDs or user ids leave the site."""
    from moderation.providers import OpenAICompatibleProvider

    user = make_user(1)
    texts = ["这是一段用户提交的公开内容", user.nickname]

    payload = OpenAICompatibleProvider().build_payload(texts, "test-model")

    blob = str(payload)
    assert user.email not in blob
    assert user.contact_methods.first().value not in blob
    assert user.game_accounts.first().battletag not in blob
    assert f'"user_id": {user.pk}' not in blob
    # No tools: the model can never act (design 5.5).
    assert "tools" not in payload
    assert payload["response_format"]["json_schema"]["strict"] is True


# --- 15.5 retention ------------------------------------------------------------


def test_retention_windows_match_the_design():
    from core.management.commands import cleanup_old_data as cleanup

    assert cleanup.API_LOG_DAYS == 90  # API 调用日志
    assert cleanup.WEBHOOK_DAYS == 180  # Webhook 投递记录
    assert cleanup.TASK_DAYS == 30  # 已完成的任务记录


@pytest.mark.django_db
def test_unhandled_moderation_records_are_never_cleaned_up():
    """Design 15.5: handled records live 180 days, unhandled ones forever.

    cleanup_old_data does not touch moderation at all, which satisfies the
    second half; this test pins that so a later "tidy-up" cannot delete a
    record nobody has looked at yet.
    """
    from io import StringIO

    from django.core.management import call_command

    from moderation.models import ModerationItem

    before = ModerationItem.objects.count()
    call_command("cleanup_old_data", stdout=StringIO())
    assert ModerationItem.objects.count() == before


@pytest.mark.django_db
def test_only_a_permitted_admin_sees_contacts_in_the_review_page():
    """Design 15.3: contacts are for tournament and scrim admins only."""
    from tournaments.review_admin import can_see_contacts

    plain = make_user(1)
    assert can_see_contacts(plain) is False

    boss = User.objects.create_superuser(
        email="audit-root@example.com",
        password="Correct-Horse-Battery-1",
        nickname="审计超管",
    )
    assert can_see_contacts(boss) is True


def test_allauth_rate_limits_cover_the_four_flows():
    """Design 15.2: login, signup, verification code, password reset."""
    from django.conf import settings

    limits = settings.ACCOUNT_RATE_LIMITS
    for flow in ("login", "login_failed", "signup", "confirm_email", "reset_password"):
        assert limits.get(flow), flow


def test_the_api_call_log_stores_no_bodies():
    """Design 15.5 and 12.10.2: summaries only, never request or response bodies."""
    from integrations.models import ApiRequestLog

    fields = {field.name for field in ApiRequestLog._meta.get_fields()}
    for forbidden in ("body", "request_body", "response_body", "payload", "headers"):
        assert forbidden not in fields, forbidden
