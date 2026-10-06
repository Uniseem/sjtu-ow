"""Round 094: every email is a letter (design 10.3, v5.4).

The user, 2026-10-03: 「邮件模板你也搞个漂亮点的，要遵守邮件礼仪。最后的祝福语用
祝好！」. Each email greets by name, says the conclusion first, closes with
「祝好！」 and the signature and the date, and says why you got it; the subject
names what it is about; the HTML is the same letter in an inline-styled frame.
"""

import re

import pytest
from django.contrib.auth.models import Permission
from django.core import mail
from django.core.mail import EmailMessage

from core import letters
from core.email_art import for_browser
from core.email_samples import samples
from core.mail import ensure_text_and_html
from core.tests.test_design_system import _person, home  # noqa: F401

SAMPLES = samples()
BY_KEY = {sample.key: sample for sample in SAMPLES}

# What each subject must name (design 10.3 主题一览).
ABOUT = {
    "apply": "新的入队申请：交大龙骑",
    "apply-ok": "入队申请已通过：交大龙骑",
    "apply-no": "入队申请未通过：交大龙骑",
    "removed": "你已被移出战队：交大龙骑",
    "captain": "你已成为队长：交大龙骑",
    "disbanded": "战队已解散：交大龙骑",
    "submitted": "报名已提交：2026 秋季校内杯",
    "entered": "你已被报名参加：2026 秋季校内杯",
    "approved": "报名已通过：2026 秋季校内杯",
    "rejected": "报名已驳回：2026 秋季校内杯",
    "cancelled": "赛事已取消：2026 秋季校内杯",
    "formed": "已编入临时队伍：2026 秋季校内杯",
    "returned": "临时队伍有变化：2026 秋季校内杯",
    "left": "临时队伍成员退出：2026 秋季校内杯",
    "reminder": "内战提醒：国庆特别场 · 6v6 怀旧",
    "scrim-cancelled": "内战已取消：国庆特别场 · 6v6 怀旧",
    "patrol": "AI 巡查发现 3 条可能不妥的内容",
    "verify": "邮箱验证码",
    "reset": "找回密码验证码",
    "unknown": "这个邮箱还没有注册",
    "exists": "这个邮箱已经注册过",
    "smtp": "SMTP 测试邮件",
}


@pytest.mark.parametrize("key", sorted(ABOUT))
def test_each_subject_says_what_and_about_what(key):
    assert BY_KEY[key].subject == ABOUT[key]


@pytest.mark.parametrize("sample", SAMPLES, ids=lambda sample: sample.key)
def test_every_email_reads_as_a_letter(sample):
    """Greeting first, 「祝好！」, the signature and today's date, then why."""
    text = sample.text
    first = text.splitlines()[0]
    assert first.endswith("你好：")
    assert "\n祝好！\n" in text
    assert f"SJTU-OW\n{letters.dated()}" in text
    assert text.index("祝好！") < text.index("——")
    assert "你收到这封邮件，是因为" in text
    assert "这封邮件由系统自动发送，请不要直接回复。" in text


@pytest.mark.parametrize("sample", SAMPLES, ids=lambda sample: sample.key)
def test_every_html_is_the_same_letter_in_the_frame(sample):
    html = sample.html
    assert '<meta name="color-scheme" content="light">' in html
    assert "data-letter-head" in html and "data-letter-card" in html
    assert "祝好！" in html and letters.dated() in html
    assert "你收到这封邮件，是因为" in html
    assert html.count("这封邮件由系统自动发送") == 1
    # Mail clients drop stylesheets and scripts and hold back outside
    # pictures: the only pictures are the ones inside the message (v7.4).
    assert "<script" not in html and "<link" not in html
    assert re.findall(r'<img src="([^"]+)"', html) == ["cid:ow-mark", "cid:ow-horizon"]
    assert " class=" not in html


def test_someone_we_do_not_know_is_greeted_without_a_name():
    assert BY_KEY["unknown"].text.startswith("你好：\n")
    assert BY_KEY["entered"].text.startswith("小天使，你好：\n")


def test_the_facts_come_before_the_details_and_the_button_after():
    text = BY_KEY["entered"].text
    assert text.index("你的游戏 ID：小天使#5123") < text.index("不需要你确认")
    assert text.index("不需要你确认") < text.index("查看报名详情：")
    html = BY_KEY["entered"].html
    assert html.index("data-letter-facts") < html.index("不需要你确认")
    assert html.index("不需要你确认") < html.index("data-letter-button")
    # The raw address under the button, for when the button does not open.
    assert "按钮打不开的话" in html


def test_a_code_is_shown_large_on_its_own():
    html = BY_KEY["reset"].html
    block = html[html.index("data-letter-code") :]
    block = block[: block.index("</div>")]
    assert "730264" in block and "font-size:32px" in block
    assert "验证码：730264" in BY_KEY["reset"].text


# --- sending ---------------------------------------------------------------------


@pytest.mark.django_db
def test_send_writes_one_letter_per_person_each_by_name():
    alice = _person("alice@example.com")
    bob = _person("bob@example.com")
    letter = letters.Letter(subject="测试：甲", lead="结论。", reason="因为测试。")
    mail.outbox.clear()

    sent = letters.send(letter, [alice, "bob@example.com", alice, "nobody@example.com"])

    assert sent == 3
    assert sorted(message.to[0] for message in mail.outbox) == [
        "alice@example.com",
        "bob@example.com",
        "nobody@example.com",
    ]
    by_address = {message.to[0]: message for message in mail.outbox}
    assert by_address["alice@example.com"].body.startswith(f"{alice.nickname}，你好：")
    # A bare address of someone we know is still greeted by name.
    assert by_address["bob@example.com"].body.startswith(f"{bob.nickname}，你好：")
    assert by_address["nobody@example.com"].body.startswith("你好：")
    alternatives = by_address["alice@example.com"].alternatives
    html = {mime: content for content, mime in alternatives}["text/html"]
    assert "data-letter-card" in html


@pytest.mark.django_db
def test_a_password_reset_code_arrives_as_a_letter(client):
    person = _person("reset@example.com")
    mail.outbox.clear()

    client.post("/accounts/password/reset/", {"email": "reset@example.com"})

    (message,) = mail.outbox
    assert message.subject == "找回密码验证码"
    assert message.body.startswith(f"{person.nickname}，你好：")
    code = re.search(r"验证码：(\w+)", message.body).group(1)
    html = dict((mime, content) for content, mime in message.alternatives)
    assert code in html["text/html"]
    assert "data-letter-code" in html["text/html"]
    assert "祝好！" in message.body


@pytest.mark.django_db
def test_an_unknown_address_gets_a_letter_without_a_name(client):
    mail.outbox.clear()

    client.post("/accounts/password/reset/", {"email": "stranger@example.com"})

    (message,) = mail.outbox
    assert message.subject == "这个邮箱还没有注册"
    assert message.body.startswith("你好：\n")


def test_text_only_mail_is_framed_once_with_its_own_footer(settings):
    """Wagtail's notifications: the text greets and closes itself; what it puts
    after 「——」 goes to the frame's footer instead of being said twice. The
    address in it is this site's (Wagtail links its own pages); only those
    become links (216, D6)."""
    settings.SITE_URL = "https://example.com"
    message = EmailMessage(
        subject="页面已批准",
        body=(
            "甲，你好：\n\n页面已批准。\nhttps://example.com/page/\n\n祝好！"
            "\n\n——\n你收到这封邮件，是因为你投过稿。\n"
            "这封邮件由系统自动发送，请不要直接回复。"
        ),
        to=["a@example.com"],
    )

    html = dict(
        (mime, content) for content, mime in ensure_text_and_html(message).alternatives
    )["text/html"]

    assert "data-letter-card" in html
    assert '<a href="https://example.com/page/"' in html
    assert html.count("这封邮件由系统自动发送") == 1
    card = html[html.index("data-letter-card") : html.index("data-letter-foot")]
    assert "你收到这封邮件" not in card
    assert "甲，你好：" in card and "祝好！" in card


# --- the specimen page --------------------------------------------------------------


@pytest.mark.django_db
def test_the_email_specimens_are_for_admins_only(client, home):  # noqa: F811
    assert client.get("/_styleguide/emails/").status_code == 404
    assert client.get("/_styleguide/emails/entered/").status_code == 404
    client.force_login(_person("member@example.com"))
    assert client.get("/_styleguide/emails/").status_code == 404
    assert client.get("/_styleguide/emails/entered/").status_code == 404


@pytest.mark.django_db
def test_an_admin_sees_every_email(client, home):  # noqa: F811
    editor = _person("editor@example.com")
    editor.user_permissions.add(
        Permission.objects.get(
            content_type__app_label="wagtailadmin", codename="access_admin"
        )
    )
    client.force_login(editor)

    page = client.get("/_styleguide/emails/").content.decode()
    for sample in SAMPLES:
        assert f'data-mail-sample="{sample.key}"' in page
        assert f"/_styleguide/emails/{sample.key}/" in page

    response = client.get("/_styleguide/emails/entered/")
    assert response.status_code == 200
    # The same letter, its cid: pictures pointed at /static/ for the browser.
    html = response.content.decode()
    assert html == for_browser(BY_KEY["entered"].html)
    assert "cid:" not in html and "/static/img/email/horizon.png" in html
    # Inline styles are allowed for the email alone, and only this site frames it.
    policy = response["Content-Security-Policy"]
    assert "style-src 'unsafe-inline'" in policy
    assert "frame-ancestors 'self'" in policy
    assert response["X-Frame-Options"] == "SAMEORIGIN"
    assert client.get("/_styleguide/emails/nothing/").status_code == 404
