from pathlib import Path

from django.conf import settings
from django.template.loader import render_to_string


def test_templates_have_no_inline_style_attributes():
    root = Path(settings.BASE_DIR) / "templates"
    offenders = []
    for path in root.rglob("*.html"):
        text = path.read_text(encoding="utf-8")
        if 'style="' in text or "style='" in text:
            offenders.append(str(path.relative_to(root)))
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
