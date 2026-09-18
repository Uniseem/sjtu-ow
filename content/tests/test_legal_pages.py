"""The terms and privacy drafts, and the command that publishes them (round 060)."""

import pytest
from django.core.management import call_command

from content.management.commands.load_legal_pages import markdown_to_html
from content.models import StandardPage


def test_the_markdown_subset_becomes_rich_text():
    html = markdown_to_html(
        "<!-- 草稿说明 -->\n# 标题\n\n## 一、账号\n\n"
        "第一段，**加粗**。\n第一段第二行。\n\n"
        "- 甲\n- 乙\n\n1. 一\n2. 二\n\n### 小节\n"
    )
    assert html == (
        "<h2>一、账号</h2>"
        "<p>第一段，<b>加粗</b>。第一段第二行。</p>"
        "<ul><li>甲</li><li>乙</li></ul>"
        "<ol><li>一</li><li>二</li></ol>"
        "<h3>小节</h3>"
    )


def test_markup_in_the_draft_is_escaped():
    assert markdown_to_html("<script>alert(1)</script>") == (
        "<p>&lt;script&gt;alert(1)&lt;/script&gt;</p>"
    )


@pytest.fixture
def pages(db):
    call_command("init_site", verbosity=0)
    return StandardPage.objects.get(slug="terms"), StandardPage.objects.get(
        slug="privacy"
    )


def _body(slug):
    return str(StandardPage.objects.get(slug=slug).body[0].value)


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
    (tmp_path / "terms.md").write_text("## 旧版\n", encoding="utf-8")
    (tmp_path / "privacy.md").write_text("## 旧版\n", encoding="utf-8")
    call_command("load_legal_pages", source=tmp_path, verbosity=0)

    (tmp_path / "terms.md").write_text("## 新版\n", encoding="utf-8")
    call_command("load_legal_pages", source=tmp_path, verbosity=0)
    assert "旧版" in _body("terms")

    call_command("load_legal_pages", source=tmp_path, force=True, verbosity=0)
    assert "新版" in _body("terms")


def test_the_privacy_draft_names_every_processor_the_site_uses(settings):
    """Design 15.3: the policy must name who processes the data."""
    text = (settings.BASE_DIR / "content" / "legal" / "privacy.md").read_text()
    for processor in ("DeepSeek", "Cloudflare", "发信服务商"):
        assert processor in text
    # Design 3.8: the rights the policy promises exist on the site.
    for right in ("导出我的个人信息", "注销"):
        assert right in text
