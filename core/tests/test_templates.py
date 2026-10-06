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


def _page_templates():
    roots = [Path(settings.BASE_DIR) / "templates"]
    roots.extend(sorted(Path(settings.BASE_DIR).glob("*/templates")))
    for root in roots:
        if not root.is_dir():
            continue
        for path in root.rglob("*.html"):
            text = path.read_text(encoding="utf-8")
            if not _is_email(path, text):
                yield path, text


def test_templates_have_no_inline_scripts_or_event_attributes():
    """The CSP forbids inline script (design 15.2): an onclick= or a <script>
    without src would be blocked in the browser and do nothing, and only a
    browser run would notice. The style scan above did not look for these
    (216, F8)."""
    import re

    handler = re.compile(r"""\son[a-z]+\s*=\s*["'{]""", re.I)
    script = re.compile(r"<script\b([^>]*)>", re.I)
    allowed = ('type="speculationrules"', 'type="application/json"')
    offenders = []
    for path, text in _page_templates():
        name = str(path.relative_to(settings.BASE_DIR))
        if handler.search(text):
            offenders.append(f"{name}: on…=")
        for attributes in script.findall(text):
            if "src=" in attributes or any(ok in attributes for ok in allowed):
                continue
            offenders.append(f"{name}: <script{attributes}>")
    assert offenders == []


def test_the_inline_script_scan_finds_what_it_is_for():
    import re

    handler = re.compile(r"""\son[a-z]+\s*=\s*["'{]""", re.I)
    assert handler.search('<button onclick="go()">')
    assert not handler.search('<a href="/on=1">')


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
