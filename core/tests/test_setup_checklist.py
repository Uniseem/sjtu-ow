"""Round 122: what a new site owner has to set up, and how they find out.

The dashboard's 「上线清单」, init_site filling the agreement pages and
saying what comes next, and the review page's 「试一下」.
"""

import io
import re
from unittest import mock

import pytest
from allauth.account.models import EmailAddress
from django.contrib.auth.models import Group
from django.core.management import call_command
from django.urls import reverse
from django.utils import timezone
from wagtail.rich_text import RichText

from accounts.models import User
from content.models import StandardPage
from core.admin_setup import setup_checks
from core.models import SiteSettings
from moderation.models import ModerationUsage, Risk
from moderation.providers import ProviderResult, Verdict

PASSWORD = "Correct-Horse-Battery-1"


@pytest.fixture
def site(db):
    call_command("init_site", verbosity=0, stdout=io.StringIO())


def _user(email, *groups, superuser=False):
    user = User.objects.create_user(
        email=email,
        password=PASSWORD,
        nickname=email.split("@")[0][:12],
        is_superuser=superuser,
        agreed_terms_at=timezone.now(),
        agreed_cross_border_at=timezone.now(),
    )
    EmailAddress.objects.create(user=user, email=email, verified=True, primary=True)
    for name in groups:
        user.groups.add(Group.objects.get(name=name))
    return user


def _panel(client):
    html = client.get("/admin/").content.decode()
    start = html.find('id="site-setup-heading"')
    if start < 0:
        return None
    return html[start : html.find("</section>", start)]


def _section(panel, name):
    found = re.search(rf'data-setup="{name}">(.*?)</ul>', panel, re.S)
    return found.group(1) if found else ""


def _check(label):
    return next(check for check in setup_checks() if check.label == label)


# --- the checklist -----------------------------------------------------


@pytest.mark.django_db
def test_mail_is_a_must_until_smtp_is_set(site, client):
    client.force_login(_user("owner122@example.com", superuser=True))
    assert "邮件（SMTP）" in _section(_panel(client), "required")
    settings_row = SiteSettings.load()
    settings_row.smtp_host = "smtp.example.com"
    settings_row.from_address = "noreply@example.com"
    settings_row.save()
    panel = _panel(client)
    assert "邮件（SMTP）" not in _section(panel, "required")
    assert "邮件（SMTP）" in _section(panel, "done")


@pytest.mark.django_db
def test_the_agreements_need_their_blanks_filled(site):
    terms = _check("用户协议")
    assert not terms.done
    assert "处【】" in terms.detail
    page = StandardPage.objects.get(slug="terms")
    page.body = [("paragraph", RichText("<p>一、账号：由守望先锋社团运营。</p>"))]
    page.save_revision().publish()
    assert _check("用户协议").done
    page.body = []
    page.save_revision().publish()
    empty = _check("用户协议")
    assert not empty.done
    assert "还没有正文" in empty.detail


@pytest.mark.django_db
def test_ai_says_whether_the_key_or_the_switch_is_missing(site, settings):
    settings.MODERATION_API_KEY = ""
    settings.MODERATION_BASE_URL = ""
    assert "MODERATION_API_KEY" in _check("AI 内容审核").detail
    settings.MODERATION_API_KEY = "sk-test"
    row = SiteSettings.load()
    row.moderation_enabled = False
    row.save()
    assert "关着" in _check("AI 内容审核").detail
    row.moderation_enabled = True
    row.save()
    assert _check("AI 内容审核").done


@pytest.mark.django_db
def test_suggestions_turn_done(site, settings):
    assert not _check("内容编辑").done
    _user("editor122@example.com", "内容编辑")
    assert _check("内容编辑").done
    settings.TEST_ENVIRONMENT = True
    assert not _check("测试环境标记").done
    settings.TEST_ENVIRONMENT = False
    assert _check("测试环境标记").done
    settings.BACKUP_ENCRYPTION_KEY = ""
    assert "BACKUP_ENCRYPTION_KEY" in _check("异地备份").detail
    row = SiteSettings.load()
    row.backup_s3_enabled = True
    row.save()
    # Uploading without the encryption key is not done either.
    assert not _check("异地备份").done
    settings.BACKUP_ENCRYPTION_KEY = "k"
    assert _check("异地备份").done
    assert "QQ 群链接" in _check("首页和分享信息").detail
    assert not _check("关于我们").done
    assert not _check("默认封面和默认头像").done


@pytest.mark.django_db
def test_only_superusers_see_the_checklist(site, client):
    client.force_login(_user("editor122b@example.com", "内容编辑"))
    assert _panel(client) is None


# --- init_site ---------------------------------------------------------


@pytest.mark.django_db
def test_init_site_fills_the_agreements_and_says_what_is_next(client):
    out = io.StringIO()
    call_command("init_site", stdout=out)
    assert "一、账号" in client.get("/terms/").content.decode()
    assert "存储地点（个人信息出境）" in client.get("/privacy/").content.decode()
    text = out.getvalue()
    assert "接下来" in text
    assert "上线清单" in text
    page = StandardPage.objects.get(slug="terms")
    page.body = [("paragraph", RichText("<p>社团改过的协议</p>"))]
    page.save_revision().publish()
    call_command("init_site", stdout=io.StringIO())
    assert "社团改过的协议" in client.get("/terms/").content.decode()


# --- 「试一下」 ---------------------------------------------------------


def _result(risk, reason="", tokens=(120, 30)):
    return ProviderResult(
        verdicts=[Verdict(index=0, risk=risk, reason=reason)],
        model="deepseek-test",
        input_tokens=tokens[0],
        output_tokens=tokens[1],
    )


@pytest.mark.django_db
def test_trying_the_ai_reports_success_and_counts_the_call(site, client, settings):
    settings.MODERATION_API_KEY = "sk-test"
    client.force_login(_user("try122@example.com", "内容编辑"))
    page = client.get(reverse("moderation_index")).content.decode()
    assert "试一下" in page
    provider = mock.Mock()
    provider.review.return_value = _result(Risk.NONE)
    with mock.patch("moderation.providers.get_provider", return_value=provider):
        response = client.post(reverse("moderation_try"), follow=True)
    assert "AI 审核能用" in response.content.decode()
    assert "无风险" in response.content.decode()
    assert ModerationUsage.objects.get().calls == 1


@pytest.mark.django_db
def test_a_bad_key_says_so(site, client, settings):
    settings.MODERATION_API_KEY = "sk-wrong"
    client.force_login(_user("try122b@example.com", "内容编辑"))
    provider = mock.Mock()
    provider.review.return_value = _result(Risk.UNKNOWN, "调用失败：HTTP 401", (0, 0))
    with mock.patch("moderation.providers.get_provider", return_value=provider):
        response = client.post(reverse("moderation_try"), follow=True)
    html = response.content.decode()
    assert "连不上 AI 审核" in html
    assert "密钥不对" in html


@pytest.mark.django_db
def test_without_a_key_the_page_says_why_and_offers_no_try(site, client, settings):
    settings.MODERATION_API_KEY = ""
    settings.MODERATION_BASE_URL = ""
    client.force_login(_user("try122c@example.com", "内容编辑"))
    page = client.get(reverse("moderation_index")).content.decode()
    assert "MODERATION_API_KEY" in page
    assert 'action="/admin/moderation/try/"' not in page
    response = client.post(reverse("moderation_try"), follow=True)
    assert "MODERATION_API_KEY" in response.content.decode()
