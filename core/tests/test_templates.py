from pathlib import Path

from django.conf import settings
from django.template.loader import render_to_string


def _is_email(path, text) -> bool:
    """Emails are styled inline because mail clients drop stylesheets (design
    10.3); they are never served as site pages, so the CSP does not apply.
    Only the email frame, its parts, and templates that extend the frame count."""
    relative = path.relative_to(settings.BASE_DIR).as_posix()
    return relative.startswith("templates/email/") or (
        relative.startswith("templates/account/email/")
        and '{% extends "email/layout.html" %}' in text
    )


def test_only_emails_may_style_inline():
    """The exemption covers emails and nothing else: a page template, or an
    allauth template that is not in the email frame, is still checked."""
    base = Path(settings.BASE_DIR)
    assert _is_email(base / "templates/email/layout.html", "")
    framed = '{% extends "email/layout.html" %}'
    assert _is_email(base / "templates/account/email/x_message.html", framed)
    assert not _is_email(base / "templates/account/email/x_message.html", "<p>")
    assert not _is_email(base / "templates/base.html", framed)
    assert not _is_email(base / "core/templates/core/styleguide_emails.html", "")


def test_templates_have_no_inline_style_attributes():
    roots = [Path(settings.BASE_DIR) / "templates"]
    roots.extend(sorted(Path(settings.BASE_DIR).glob("*/templates")))
    offenders = []
    for root in roots:
        if not root.is_dir():
            continue
        for path in root.rglob("*.html"):
            text = path.read_text(encoding="utf-8")
            if _is_email(path, text):
                continue
            if 'style="' in text or "style='" in text:
                offenders.append(str(path.relative_to(settings.BASE_DIR)))
    assert offenders == []


def test_django_error_pages_reference_only_error_css():
    pages = [
        ("errors/404.html", {}),
        ("errors/403.html", {"reason": "你没有权限查看这个页面。"}),
        ("errors/429.html", {"retry_after": None}),
        ("errors/500.html", {"request_id": "abc"}),
    ]
    for template, context in pages:
        html = render_to_string(template, context)
        lower = html.lower()
        assert "<style" not in lower, template
        assert "<script" not in lower, template
        assert lower.count('rel="stylesheet"') == 1, template
        assert "error.css" in html, template
        assert "/static/css/app.css" not in html, template


def test_maintenance_page_is_self_contained_and_inlines_error_css():
    html = (
        Path(settings.BASE_DIR) / "deploy" / "error_pages" / "maintenance.html"
    ).read_text(encoding="utf-8")
    css = (Path(settings.BASE_DIR) / "static" / "css" / "error.css").read_text(
        encoding="utf-8"
    )
    lower = html.lower()
    assert "/static/" not in html
    assert "<link" not in lower
    assert "<script" not in lower
    assert ".actions a.secondary" in html
    assert ".actions a.secondary" in css
