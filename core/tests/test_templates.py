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


def test_error_page_templates_do_not_reference_static_files():
    pages = [
        ("errors/404.html", {}),
        ("errors/403.html", {"reason": "你没有权限查看这个页面。"}),
        ("errors/429.html", {"retry_after": None}),
        ("errors/500.html", {"request_id": "abc"}),
        ("errors/maintenance.html", {}),
    ]
    for template, context in pages:
        html = render_to_string(template, context)
        assert "/static/" not in html, template
        assert "{% static" not in html, template
        assert 'rel="stylesheet"' not in html.lower(), template
        assert "<script" not in html.lower(), template
