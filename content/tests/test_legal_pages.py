"""The terms and privacy drafts, and the command that publishes them (round 060)."""

import pytest
from django.core.management import call_command

from content.management.commands.load_legal_pages import body_from_draft
from content.models import StandardPage


def test_the_draft_goes_in_as_markdown_without_the_note_and_title():
    """v6.70: bodies are Markdown, so the draft is stored as written, minus
    the note to the club and its own # title (the page title)."""
    body = body_from_draft(
        "<!-- 草稿说明 -->\n# 标题\n\n## 一、账号\n\n第一段，**加粗**。\n"
    )
    assert body == "## 一、账号\n\n第一段，**加粗**。"


def test_markup_in_the_draft_is_escaped_on_the_page():
    from content.markdown import render

    assert str(render(body_from_draft("<script>alert(1)</script>"))) == (
        "<p>&lt;script&gt;alert(1)&lt;/script&gt;</p>\n"
    )


@pytest.fixture
def pages(db):
    call_command("init_site", verbosity=0)
    return StandardPage.objects.get(slug="terms"), StandardPage.objects.get(
        slug="privacy"
    )


def _body(slug):
    return StandardPage.objects.get(slug=slug).body


@pytest.mark.django_db
def test_the_command_publishes_both_drafts(pages, client):
    call_command("load_legal_pages", verbosity=0)

    terms = client.get("/terms/").content.decode("utf-8")
    privacy = client.get("/privacy/").content.decode("utf-8")
    assert "一、账号" in terms
    assert "存储地点（个人信息出境）" in privacy
    for html in (terms, privacy):
        assert "**" not in html
        assert "## " not in html


@pytest.mark.django_db
def test_an_edited_page_is_not_overwritten_without_force(pages, tmp_path):
    # init_site already filled the pages from the drafts (round 122), so the
    # first version goes in with --force, standing in for an editor's text.
    (tmp_path / "terms.md").write_text("## 旧版\n", encoding="utf-8")
    (tmp_path / "privacy.md").write_text("## 旧版\n", encoding="utf-8")
    call_command("load_legal_pages", source=tmp_path, force=True, verbosity=0)

    (tmp_path / "terms.md").write_text("## 新版\n", encoding="utf-8")
    call_command("load_legal_pages", source=tmp_path, verbosity=0)
    assert "旧版" in _body("terms")

    call_command("load_legal_pages", source=tmp_path, force=True, verbosity=0)
    assert "新版" in _body("terms")


def test_the_privacy_draft_names_every_processor_the_site_uses(settings):
    """Design 15.3: the policy must name who processes the data."""
    text = (settings.BASE_DIR / "content" / "legal" / "privacy.md").read_text(
        encoding="utf-8"
    )
    # Round 209: the ones actually in use (the AI check, the mail service,
    # the server and the forwarding server in front of it).
    for processor in ("DeepSeek", "网易 126 邮箱", "Contabo", "ZgoCloud", "Cloudflare"):
        assert processor in text
    assert "【" not in text  # nothing left for the club to fill in
    # Design 3.8: the rights the policy promises exist on the site.
    for right in ("导出我的个人信息", "注销"):
        assert right in text


@pytest.mark.django_db
def test_the_command_asks_for_init_site_first():
    """Round 179: no page to fill is a clear message, not a traceback."""
    from django.core.management.base import CommandError

    with pytest.raises(CommandError, match="init_site"):
        call_command("load_legal_pages", verbosity=0)
