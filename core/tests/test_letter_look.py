"""Round 200 (design 10.3, v7.4): the letters look like the site.

The user, 10-05: 「现在上面那个配色一股 AI 味，请采用 SVG 风格，就是我们站点的风
格，且以交大红为主色」, and the address under the button 「改成原文链接」. An SJTU
red head with the site mark and the site's two ridges (pictures inside the
message, since mail clients show no SVG), nothing outlined, a red pill, and
the address written as people read it.
"""

import re
from email import message_from_bytes, policy

import pytest
from django.core import mail
from django.core.mail import EmailMessage
from PIL import Image

from core import email_art, letters
from core.email_samples import samples
from core.mail import (
    LetterMessage,
    deliver_email_payload,
    ensure_text_and_html,
    serialize_email,
)
from core.templatetags.ow import readable_url

BY_KEY = {sample.key: sample for sample in samples()}
CHINESE = (
    "https://example.com/news/%E7%BD%91%E7%AB%99%E6%AD%A3%E5%BC%8F%E5%8F%91%E5%B8%83/"
)


def _letter(url=CHINESE):
    return letters.Letter(
        subject="测试：原文链接",
        lead="结论。",
        facts=[("赛事", "秋季杯"), ("时间", "周五")],
        action=("打开", url),
        reason="因为测试。",
    )


def _parts(message):
    """(content type, Content-ID, disposition) of each leaf, in order."""
    built = message_from_bytes(message.message().as_bytes(), policy=policy.default)
    return built, [
        (part.get_content_type(), part["Content-ID"], part.get_content_disposition())
        for part in built.walk()
        if not part.is_multipart()
    ]


# --- the look --------------------------------------------------------------------


@pytest.mark.parametrize("key", ["entered", "verify", "patrol", "smtp"])
def test_the_head_is_sjtu_red_with_the_site_mark_and_ridges(key):
    html = BY_KEY[key].html
    head = html[html.index("data-letter-head") : html.index("data-letter-card")]
    assert 'bgcolor="#9b3a33"' in head and "background-color:#9b3a33" in head
    assert 'src="cid:ow-mark"' in head and 'src="cid:ow-horizon"' in head
    assert "交大守望先锋" in head and "上海交通大学守望先锋社区" in head
    # v5's night head and orange rule are gone.
    assert "#141a24" not in html and "#cf9152" not in html


def test_nothing_is_outlined_and_the_button_is_a_red_pill():
    html = BY_KEY["entered"].html
    assert "1px solid" not in html
    card = html[html.index("data-letter-card") :]
    assert card[: card.index(">")].count("border-radius:0 0 16px 16px") == 1
    button = html[html.index("data-letter-button") :]
    assert "background-color:#9b3a33;border-radius:999px" in button[:200]
    facts = html[html.index("data-letter-facts") :]
    assert "background-color:#eef0f3;border-radius:12px" in facts[:200]
    assert "border-top:2px solid #ffffff" in facts[: facts.index("</table>")]


def test_the_address_under_the_button_reads_as_written():
    html = letters.html_of(_letter())
    box = html[html.index("data-letter-url") :]
    box = box[: box.index("</div>")]
    assert "https://example.com/news/网站正式发布/" in box
    assert f'href="{CHINESE}"' in box  # still the encoded address
    assert "user-select:all" in box
    # The plain text keeps the encoded address (plain-text Chinese links break).
    assert CHINESE in letters.text_of(_letter())


def test_only_escaped_text_is_turned_back():
    assert readable_url("/a/%E7%BD%91%E7%AB%99/") == "/a/网站/"
    # Escaped ASCII keeps its meaning; bytes that are not UTF-8 stay.
    assert readable_url("/q?x=%3F%2F") == "/q?x=%3F%2F"
    assert readable_url("/bad/%FF%FE/") == "/bad/%FF%FE/"
    assert readable_url("") == ""


# --- the pictures go inside -----------------------------------------------------


def test_a_letter_carries_its_pictures_inside():
    built, parts = _parts(letters.message(_letter(), "a@example.com", "甲"))
    assert built.get_content_type() == "multipart/alternative"
    assert parts[0][0] == "text/plain"
    assert parts[1][0] == "text/html"
    assert parts[2:] == [
        ("image/png", "<ow-mark>", "inline"),
        ("image/png", "<ow-horizon>", "inline"),
    ]
    related = [p for p in built.walk() if p.get_content_type() == "multipart/related"]
    assert len(related) == 1
    pictures = [
        p for p in related[0].iter_parts() if p.get_content_type() == "image/png"
    ]
    assert (
        pictures[1].get_content() == (email_art.folder() / "horizon.png").read_bytes()
    )


@pytest.mark.django_db
def test_queued_mail_gets_its_pictures_on_the_way_out(settings):
    """allauth's and the other templates' mail goes through the queue: the
    worker builds a LetterMessage and the pictures go along."""
    settings.EMAIL_DELIVERY_BACKEND = "django.core.mail.backends.locmem.EmailBackend"
    mail.outbox.clear()
    payload = serialize_email(letters.message(_letter(), "q@example.com"))
    assert deliver_email_payload(payload) == 1
    (sent,) = mail.outbox
    assert isinstance(sent, LetterMessage)
    _built, parts = _parts(sent)
    assert [cid for _type, cid, _d in parts if cid] == ["<ow-mark>", "<ow-horizon>"]


def test_mail_without_pictures_carries_none():
    message = LetterMessage(subject="无图", body="正文", to=["a@example.com"])
    message.attach_alternative("<p>正文</p>", "text/html")
    _built, parts = _parts(message)
    assert [kind for kind, _cid, _d in parts] == ["text/plain", "text/html"]


def test_text_only_mail_gets_the_same_head():
    """Wagtail's notifications are framed by core.mail with the same head."""
    message = EmailMessage(
        subject="通知", body="甲，你好：\n\n正文。", to=["a@example.com"]
    )
    framed = ensure_text_and_html(message)
    html = dict((mime, c) for c, mime in framed.alternatives)["text/html"]
    assert 'src="cid:ow-horizon"' in html
    assert isinstance(framed, LetterMessage)


# --- the files ----------------------------------------------------------------------


def test_the_committed_pictures_match_what_the_code_draws():
    """After changing core/email_art.py, run render_email_art and commit."""
    for name, drawn in email_art.files().items():
        committed = Image.open(email_art.folder() / name).convert("RGBA")
        assert committed.size == drawn.size, name
        assert committed.tobytes() == drawn.convert("RGBA").tobytes(), name


def test_the_ridges_sit_on_red_and_run_into_the_white_card():
    strip = email_art.horizon().convert("RGBA")
    assert strip.size == (email_art.WIDTH, email_art.HEIGHT)
    assert strip.getpixel((5, 0)) == email_art.PRIMARY
    bottom = {strip.getpixel((x, strip.height - 1)) for x in range(0, strip.width, 37)}
    assert bottom == {email_art.WHITE}
    # The far ridge's half-tone lies between the red and the white as a band,
    # not just as the blend along one edge: several pixels deep in most columns.
    columns = range(0, strip.width, 23)
    banded = sum(
        sum(strip.getpixel((x, y)) == email_art.FAR for y in range(strip.height)) >= 6
        for x in columns
    )
    assert banded > len(columns) * 0.8


def test_the_mark_is_the_site_icon_the_other_way_round():
    mark = email_art.mark().convert("RGBA")
    assert mark.size == (email_art.MARK, email_art.MARK)
    scale = email_art.MARK / 32
    corner = mark.getpixel((round(4 * scale), round(16 * scale)))
    tip = mark.getpixel((round(16 * scale), round(13.5 * scale)))
    assert corner == email_art.WHITE
    assert (
        max(abs(a - b) for a, b in zip(tip[:3], email_art.PRIMARY[:3], strict=True))
        < 30
    )


def test_the_specimen_page_points_the_pictures_at_static():
    html = email_art.for_browser(BY_KEY["entered"].html)
    assert "cid:" not in html
    assert re.findall(r'<img src="([^"]+)"', html) == [
        "/static/img/email/mark.png",
        "/static/img/email/horizon.png",
    ]
